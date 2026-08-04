#define _POSIX_C_SOURCE 200809L

#include "elpis/corpus.h"
#include "elpis/chunking.h"
#include "elpis/sha256.h"

#include <sqlite3.h>

#include <cerrno>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <string>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <vector>

struct elpis_corpus {
    sqlite3 *db = nullptr;
    std::string root;
    std::string blobs;
    std::string error;
};

namespace {

void set_error(elpis_corpus *c, const std::string &s) { if (c) c->error = s; }
void set_sql_error(elpis_corpus *c, const char *prefix) {
    set_error(c, std::string(prefix) + ": " + (c && c->db ? sqlite3_errmsg(c->db) : "no database"));
}

bool valid_token(const char *s, size_t max_len) {
    if (!s || !*s) return false;
    size_t n = std::strlen(s);
    if (n > max_len) return false;
    for (size_t i=0;i<n;++i) {
        unsigned char ch=(unsigned char)s[i];
        if (ch < 0x20 || ch == 0x7f) return false;
    }
    return true;
}

bool valid_hex64(const char *s) {
    if (!s) return false;
    for (size_t i = 0; i < 64; ++i) {
        unsigned char c = (unsigned char)s[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    }
    return s[64] == '\0';
}

bool valid_authority(const char *s) {
    return s && (!std::strcmp(s,"canonical") || !std::strcmp(s,"reference") ||
                 !std::strcmp(s,"advisory") || !std::strcmp(s,"provisional"));
}

bool valid_media(const char *s) {
    return s && (!std::strcmp(s,ELPIS_MT_TEXT) || !std::strcmp(s,ELPIS_MT_MARKDOWN) ||
                 !std::strcmp(s,ELPIS_MT_CODE) || !std::strcmp(s,ELPIS_MT_JSON) ||
                 !std::strcmp(s,ELPIS_MT_JSONL));
}

int mkdir_one(const std::string &p) {
    if (::mkdir(p.c_str(),0700)==0 || errno==EEXIST) return 0;
    return -1;
}

int mkdir_p(const std::string &p) {
    if (p.empty()) return -1;
    std::string cur;
    if (p[0]=='/') cur="/";
    size_t i=0;
    while (i<p.size()) {
        while (i<p.size() && p[i]=='/') ++i;
        size_t j=i; while (j<p.size() && p[j]!='/') ++j;
        if (j==i) break;
        if (cur.size()>1 && cur.back()!='/') cur.push_back('/');
        cur.append(p,i,j-i);
        if (mkdir_one(cur)!=0) return -1;
        i=j;
    }
    return 0;
}

int write_all(int fd, const void *data, size_t len) {
    const unsigned char *p=(const unsigned char *)data;
    while (len) {
        ssize_t n=::write(fd,p,len);
        if (n<0) { if (errno==EINTR) continue; return -1; }
        if (n==0) return -1;
        p+=(size_t)n; len-=(size_t)n;
    }
    return 0;
}

int read_all(int fd, void *data, size_t len) {
    unsigned char *p=(unsigned char *)data;
    while (len) {
        ssize_t n=::read(fd,p,len);
        if (n<0) { if (errno==EINTR) continue; return -1; }
        if (n==0) return -1;
        p+=(size_t)n; len-=(size_t)n;
    }
    return 0;
}

int fsync_parent(const std::string &path) {
    size_t slash=path.find_last_of('/');
    std::string parent=slash==std::string::npos ? "." : path.substr(0,slash);
    int fd=::open(parent.c_str(),O_RDONLY|O_DIRECTORY);
    if (fd<0) return -1;
    int rc=::fsync(fd); ::close(fd); return rc;
}

int write_blob_atomic(elpis_corpus *c, const std::string &final,
                      const void *bytes, size_t len) {
    if (::access(final.c_str(),F_OK)==0) return 0;
    std::string tmp=c->blobs+"/.ingest-XXXXXX";
    std::vector<char> name(tmp.begin(),tmp.end()); name.push_back('\0');
    int fd=::mkstemp(name.data());
    if (fd<0) { set_error(c,"mkstemp failed"); return -1; }
    int rc=0;
    if (write_all(fd,bytes,len)!=0 || ::fsync(fd)!=0) rc=-1;
    if (::close(fd)!=0) rc=-1;
    if (rc==0 && ::rename(name.data(),final.c_str())!=0) {
        if (errno==EEXIST) ::unlink(name.data()); else rc=-1;
    }
    if (rc==0 && fsync_parent(final)!=0) rc=-1;
    if (rc!=0) { ::unlink(name.data()); set_error(c,"atomic blob write failed"); }
    return rc;
}

int exec_sql(elpis_corpus *c, const char *sql) {
    char *err=nullptr;
    int rc=sqlite3_exec(c->db,sql,nullptr,nullptr,&err);
    if (rc!=SQLITE_OK) {
        set_error(c,err ? err : sqlite3_errmsg(c->db)); sqlite3_free(err); return -1;
    }
    return 0;
}

struct Stmt {
    sqlite3_stmt *p=nullptr;
    ~Stmt(){ if(p) sqlite3_finalize(p); }
};

int prepare(elpis_corpus *c, Stmt &s, const char *sql) {
    if (sqlite3_prepare_v2(c->db,sql,-1,&s.p,nullptr)!=SQLITE_OK) { set_sql_error(c,"prepare"); return -1; }
    return 0;
}

std::string json_escape(const unsigned char *s, size_t n) {
    static const char h[]="0123456789abcdef";
    std::string o; o.reserve(n+8); o.push_back('"');
    for (size_t i=0;i<n;++i) {
        unsigned char c=s[i];
        switch(c) {
        case '"': o+="\\\""; break; case '\\': o+="\\\\"; break;
        case '\b': o+="\\b"; break; case '\f': o+="\\f"; break;
        case '\n': o+="\\n"; break; case '\r': o+="\\r"; break; case '\t': o+="\\t"; break;
        default:
            if (c<0x20) { o+="\\u00"; o.push_back(h[c>>4]); o.push_back(h[c&15]); }
            else o.push_back((char)c);
        }
    }
    o.push_back('"'); return o;
}

std::string literal_fts_query(const char *q) {
    std::string out="\"";
    for (const char *p=q; *p; ++p) { if (*p=='\"') out+="\"\""; else out.push_back(*p); }
    out.push_back('\"'); return out;
}

int file_digest(const std::string &path, uint64_t expected, char out[65]) {
    int fd=::open(path.c_str(),O_RDONLY);
    if(fd<0) return -1;
    struct stat st{};
    if(::fstat(fd,&st)!=0 || (uint64_t)st.st_size!=expected) { ::close(fd); return -1; }
    elpis_sha256_ctx h; elpis_sha256_init(&h);
    unsigned char buf[65536];
    for (;;) {
        ssize_t n=::read(fd,buf,sizeof buf);
        if(n<0){ if(errno==EINTR) continue; ::close(fd); return -1; }
        if(n==0) break;
        elpis_sha256_update(&h,buf,(size_t)n);
    }
    ::close(fd); uint8_t d[32]; elpis_sha256_final(&h,d); elpis_hex32(d,out); return 0;
}

void copy_text(char *dst, size_t cap, const unsigned char *src) {
    if (!dst || !cap) return;
    if (!src) { dst[0]=0; return; }
    std::snprintf(dst,cap,"%s",(const char *)src);
}

} // namespace

extern "C" {

int elpis_corpus_open(const char *state_root, elpis_corpus **out) {
    if (!state_root || !*state_root || !out) return -1;
    *out=nullptr;
    elpis_corpus *c=new(std::nothrow) elpis_corpus;
    if(!c) return -1;
    c->root=state_root; c->blobs=c->root+"/corpus";
    if(mkdir_p(c->root)!=0 || mkdir_p(c->blobs)!=0) { delete c; return -1; }
    std::string dbpath=c->root+"/metadata.sqlite";
    if (sqlite3_open_v2(dbpath.c_str(), &c->db,
                        SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX,
                        nullptr) != SQLITE_OK) {
        if (c->db) sqlite3_close(c->db);
        delete c;
        return -1;
    }
    sqlite3_busy_timeout(c->db,5000);
    if(exec_sql(c,"PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;")!=0 ||
       exec_sql(c,
        "CREATE TABLE IF NOT EXISTS documents("
        " digest TEXT PRIMARY KEY CHECK(length(digest)=64),"
        " bytes INTEGER NOT NULL CHECK(bytes>=0), media_type TEXT NOT NULL,"
        " namespace TEXT NOT NULL, authority TEXT NOT NULL, origin TEXT NOT NULL,"
        " chunk_profile_digest TEXT NOT NULL CHECK(length(chunk_profile_digest)=64));"
        "CREATE TABLE IF NOT EXISTS chunks("
        " digest TEXT PRIMARY KEY CHECK(length(digest)=64),"
        " doc_digest TEXT NOT NULL REFERENCES documents(digest) ON DELETE CASCADE,"
        " ordinal INTEGER NOT NULL, byte_start INTEGER NOT NULL, byte_end INTEGER NOT NULL,"
        " norm_digest TEXT NOT NULL CHECK(length(norm_digest)=64), text TEXT NOT NULL,"
        " UNIQUE(doc_digest,ordinal));"
        "CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(doc_digest,ordinal);"
        "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5("
        " text, chunk_digest UNINDEXED, doc_digest UNINDEXED, namespace UNINDEXED, authority UNINDEXED,"
        " tokenize=\"unicode61 tokenchars '_.,:'\");")!=0) {
        sqlite3_close(c->db); delete c; return -1;
    }
    *out=c; return 0;
}

void elpis_corpus_close(elpis_corpus *c) {
    if(!c) return;
    if(c->db) sqlite3_close(c->db);
    delete c;
}

const char *elpis_corpus_error(const elpis_corpus *c) { return c ? c->error.c_str() : "null corpus"; }

int elpis_corpus_ingest_bytes(elpis_corpus *c, const void *bytes, size_t len,
                              const elpis_ingest_meta *m, elpis_ingest_result *out) {
    if(!c || (!bytes && len) || !m || !out) return -1;
    std::memset(out,0,sizeof *out); c->error.clear();
    if(!valid_token(m->ns,95) || !valid_authority(m->authority) || !valid_media(m->media_type) ||
       !valid_token(m->origin,4096)) { set_error(c,"invalid ingestion metadata"); return -1; }
    uint8_t dg[32]; elpis_sha256(bytes,len,dg); elpis_hex32(dg,out->doc_digest);

    Stmt exists;
    if(prepare(c,exists,"SELECT (SELECT count(*) FROM chunks WHERE doc_digest=?1) FROM documents WHERE digest=?1;")!=0) return -1;
    sqlite3_bind_text(exists.p,1,out->doc_digest,-1,SQLITE_STATIC);
    int sr=sqlite3_step(exists.p);
    if(sr==SQLITE_ROW) { out->duplicate=1; out->chunk_count=(uint32_t)sqlite3_column_int64(exists.p,0); return 0; }
    if(sr!=SQLITE_DONE) { set_sql_error(c,"duplicate check"); return -1; }

    elpis_chunk_profile prof; elpis_chunk_profile_default(&prof);
    elpis_chunk *chunks=nullptr; size_t n_chunks=0;
    if(elpis_chunk_document(bytes,len,m->media_type,&prof,out->doc_digest,&chunks,&n_chunks)!=0) {
        set_error(c,"deterministic chunking failed"); return -1;
    }
    char pd[65];
    if(elpis_chunk_profile_digest_checked(&prof,m->media_type,pd)!=0) { elpis_chunks_free(chunks); return -1; }
    std::string blob=c->blobs+"/"+out->doc_digest+".blob";
    if(write_blob_atomic(c,blob,bytes,len)!=0) { elpis_chunks_free(chunks); return -1; }

    if(exec_sql(c,"BEGIN IMMEDIATE;")!=0) { elpis_chunks_free(chunks); ::unlink(blob.c_str()); return -1; }
    bool ok=true;
    Stmt idoc, ichunk, ifts;
    ok &= prepare(c,idoc,"INSERT INTO documents(digest,bytes,media_type,namespace,authority,origin,chunk_profile_digest) VALUES(?1,?2,?3,?4,?5,?6,?7);")==0;
    ok &= prepare(c,ichunk,"INSERT INTO chunks(digest,doc_digest,ordinal,byte_start,byte_end,norm_digest,text) VALUES(?1,?2,?3,?4,?5,?6,?7);")==0;
    ok &= prepare(c,ifts,"INSERT INTO chunks_fts(text,chunk_digest,doc_digest,namespace,authority) VALUES(?1,?2,?3,?4,?5);")==0;
    if(ok) {
        sqlite3_bind_text(idoc.p,1,out->doc_digest,-1,SQLITE_STATIC); sqlite3_bind_int64(idoc.p,2,(sqlite3_int64)len);
        sqlite3_bind_text(idoc.p,3,m->media_type,-1,SQLITE_STATIC); sqlite3_bind_text(idoc.p,4,m->ns,-1,SQLITE_STATIC);
        sqlite3_bind_text(idoc.p,5,m->authority,-1,SQLITE_STATIC); sqlite3_bind_text(idoc.p,6,m->origin,-1,SQLITE_STATIC);
        sqlite3_bind_text(idoc.p,7,pd,-1,SQLITE_STATIC);
        ok=sqlite3_step(idoc.p)==SQLITE_DONE;
    }
    for(size_t i=0; ok && i<n_chunks; ++i) {
        size_t s=(size_t)chunks[i].byte_start,e=(size_t)chunks[i].byte_end;
        size_t nn=elpis_normalize((const char *)bytes+s,e-s,nullptr,0);
        std::vector<char> norm(nn+1); elpis_normalize((const char *)bytes+s,e-s,norm.data(),norm.size());
        sqlite3_reset(ichunk.p); sqlite3_clear_bindings(ichunk.p);
        sqlite3_bind_text(ichunk.p,1,chunks[i].digest,-1,SQLITE_STATIC); sqlite3_bind_text(ichunk.p,2,out->doc_digest,-1,SQLITE_STATIC);
        sqlite3_bind_int64(ichunk.p,3,(sqlite3_int64)i); sqlite3_bind_int64(ichunk.p,4,(sqlite3_int64)s); sqlite3_bind_int64(ichunk.p,5,(sqlite3_int64)e);
        sqlite3_bind_text(ichunk.p,6,chunks[i].norm_digest,-1,SQLITE_STATIC); sqlite3_bind_text(ichunk.p,7,norm.data(),(int)nn,SQLITE_TRANSIENT);
        ok=sqlite3_step(ichunk.p)==SQLITE_DONE;
        if(!ok) break;
        sqlite3_reset(ifts.p); sqlite3_clear_bindings(ifts.p);
        sqlite3_bind_text(ifts.p,1,norm.data(),(int)nn,SQLITE_TRANSIENT); sqlite3_bind_text(ifts.p,2,chunks[i].digest,-1,SQLITE_STATIC);
        sqlite3_bind_text(ifts.p,3,out->doc_digest,-1,SQLITE_STATIC); sqlite3_bind_text(ifts.p,4,m->ns,-1,SQLITE_STATIC); sqlite3_bind_text(ifts.p,5,m->authority,-1,SQLITE_STATIC);
        ok=sqlite3_step(ifts.p)==SQLITE_DONE;
    }
    if(ok && exec_sql(c,"COMMIT;")==0) {
        out->chunk_count=(uint32_t)n_chunks; out->duplicate=0; elpis_chunks_free(chunks); return 0;
    }
    set_sql_error(c,"ingestion transaction"); exec_sql(c,"ROLLBACK;"); ::unlink(blob.c_str()); elpis_chunks_free(chunks); return -1;
}

int elpis_corpus_counts(elpis_corpus *c, uint64_t *documents, uint64_t *chunks) {
    if(!c) return -1;
    Stmt s; if(prepare(c,s,"SELECT (SELECT count(*) FROM documents),(SELECT count(*) FROM chunks);")!=0) return -1;
    if(sqlite3_step(s.p)!=SQLITE_ROW) return -1;
    if(documents) *documents=(uint64_t)sqlite3_column_int64(s.p,0);
    if(chunks) *chunks=(uint64_t)sqlite3_column_int64(s.p,1);
    return 0;
}

int elpis_corpus_search_lexical(elpis_corpus *c, const char *query, const char *ns,
                                const char *authority, uint32_t limit,
                                elpis_hit *hits, uint32_t *count) {
    if(!c || !query || !*query || !count || (limit && !hits)) return -1;
    *count=0; if(!limit) return 0;
    if(ns && !valid_token(ns,95)) return -1;
    if(authority && !valid_authority(authority)) return -1;
    std::string q=literal_fts_query(query);
    const char *sql=
      "SELECT f.doc_digest,f.chunk_digest,f.namespace,f.authority,bm25(chunks_fts),c.ordinal,c.byte_start,c.byte_end "
      "FROM chunks_fts f JOIN chunks c ON c.digest=f.chunk_digest "
      "WHERE chunks_fts MATCH ?1 AND (?2 IS NULL OR f.namespace=?2) AND (?3 IS NULL OR f.authority=?3) "
      "ORDER BY bm25(chunks_fts),f.chunk_digest LIMIT ?4;";
    Stmt s; if(prepare(c,s,sql)!=0) return -1;
    sqlite3_bind_text(s.p,1,q.c_str(),-1,SQLITE_TRANSIENT);
    if(ns) sqlite3_bind_text(s.p,2,ns,-1,SQLITE_STATIC); else sqlite3_bind_null(s.p,2);
    if(authority) sqlite3_bind_text(s.p,3,authority,-1,SQLITE_STATIC); else sqlite3_bind_null(s.p,3);
    sqlite3_bind_int(s.p,4,(int)limit);
    while(*count<limit) {
        int rc=sqlite3_step(s.p); if(rc==SQLITE_DONE) break;
        if(rc!=SQLITE_ROW) { set_sql_error(c,"lexical search"); return -1; }
        elpis_hit &h=hits[*count]; std::memset(&h,0,sizeof h);
        copy_text(h.doc_digest,sizeof h.doc_digest,sqlite3_column_text(s.p,0));
        copy_text(h.chunk_digest,sizeof h.chunk_digest,sqlite3_column_text(s.p,1));
        copy_text(h.ns,sizeof h.ns,sqlite3_column_text(s.p,2));
        copy_text(h.authority,sizeof h.authority,sqlite3_column_text(s.p,3));
        h.lexical_score=sqlite3_column_double(s.p,4); h.ordinal=(uint64_t)sqlite3_column_int64(s.p,5);
        h.byte_start=(uint64_t)sqlite3_column_int64(s.p,6); h.byte_end=(uint64_t)sqlite3_column_int64(s.p,7);
        ++*count;
    }
    return 0;
}

int elpis_corpus_document_bytes(elpis_corpus *c, const char *digest, void **out, size_t *len) {
    if (!c || !digest || !out || !len) return -1;
    *out = nullptr;
    *len = 0;
    Stmt s; if(prepare(c,s,"SELECT bytes FROM documents WHERE digest=?1;")!=0) return -1;
    sqlite3_bind_text(s.p,1,digest,-1,SQLITE_STATIC); if(sqlite3_step(s.p)!=SQLITE_ROW) return -1;
    uint64_t n=(uint64_t)sqlite3_column_int64(s.p,0); if(n>SIZE_MAX) return -1;
    std::string path=c->blobs+"/"+digest+".blob";
    int fd=::open(path.c_str(),O_RDONLY); if(fd<0) { set_error(c,"document blob missing"); return -1; }
    struct stat st{}; if(::fstat(fd,&st)!=0 || (uint64_t)st.st_size!=n) { ::close(fd); set_error(c,"document size mismatch"); return -1; }
    void *p=std::malloc(n ? (size_t)n : 1); if(!p){::close(fd);return -1;}
    if(n && read_all(fd,p,(size_t)n)!=0){std::free(p);::close(fd);return -1;} ::close(fd);
    uint8_t dg[32]; char hex[65]; elpis_sha256(p,(size_t)n,dg); elpis_hex32(dg,hex);
    if(std::strcmp(hex,digest)!=0){ std::memset(p,0,(size_t)n); std::free(p); set_error(c,"document digest mismatch"); return -1; }
    *out=p; *len=(size_t)n; return 0;
}

int elpis_corpus_chunk_text(elpis_corpus *c, const char *digest, char **out) {
    if (!c || !digest || !out) return -1;
    *out = nullptr;
    Stmt s; if(prepare(c,s,"SELECT text,norm_digest FROM chunks WHERE digest=?1;")!=0) return -1;
    sqlite3_bind_text(s.p,1,digest,-1,SQLITE_STATIC); if(sqlite3_step(s.p)!=SQLITE_ROW) return -1;
    const unsigned char *text=sqlite3_column_text(s.p,0), *expected=sqlite3_column_text(s.p,1);
    int n=sqlite3_column_bytes(s.p,0); uint8_t dg[32]; char hex[65]; elpis_sha256(text,(size_t)n,dg); elpis_hex32(dg,hex);
    if(!expected || std::strcmp(hex,(const char *)expected)!=0){set_error(c,"chunk normalized digest mismatch");return -1;}
    char *p=(char *)std::malloc((size_t)n+1); if(!p)return -1; if(n)std::memcpy(p,text,(size_t)n);p[n]=0;*out=p;return 0;
}

int elpis_corpus_verify(elpis_corpus *c, uint64_t *ok, uint64_t *bad,
                        char *first_bad, size_t first_bad_cap) {
    if (!c) return -1;
    uint64_t good = 0, broken = 0;
    if(first_bad && first_bad_cap) first_bad[0]=0;
    Stmt s; if(prepare(c,s,"SELECT digest,bytes FROM documents ORDER BY digest;")!=0)return -1;
    for(;;){int rc=sqlite3_step(s.p);if(rc==SQLITE_DONE)break;if(rc!=SQLITE_ROW)return -1;
        const char *d=(const char *)sqlite3_column_text(s.p,0);uint64_t n=(uint64_t)sqlite3_column_int64(s.p,1);
        std::string path=c->blobs+"/"+d+".blob";char got[65];
        if(file_digest(path,n,got)==0 && std::strcmp(got,d)==0)++good;
        else {++broken;if(first_bad&&first_bad_cap&&first_bad[0]==0)std::snprintf(first_bad,first_bad_cap,"%s",d);}
    }
    if (ok) *ok = good;
    if (bad) *bad = broken;
    return broken ? 1 : 0;
}

/* Additive R2 hook: read-only chunk enumeration, chunk digest ascending.
 * Namespace and authority live on the document row, so they are joined here
 * rather than duplicated onto chunks. */
static int list_chunks_impl(elpis_corpus *c, const char *namespace_filter,
                            const char *authority_filter, uint64_t offset,
                            uint32_t limit, elpis_chunk_ref *out, uint32_t *n_out) {
    if (!c || !out || !n_out || limit == 0) return -1;
    *n_out = 0;
    /* Filters are validated with exactly the policy elpis_corpus_search_lexical
     * uses, and are rejected BEFORE any statement is prepared or executed. An
     * unknown authority class is a caller error, not an empty result set. */
    if (namespace_filter && !valid_token(namespace_filter, 95)) {
        set_error(c, "list_chunks: invalid namespace filter");
        return -1;
    }
    if (authority_filter && !valid_authority(authority_filter)) {
        set_error(c, "list_chunks: invalid authority class filter");
        return -1;
    }
    std::string sql =
        "SELECT k.digest,k.doc_digest,d.namespace,d.authority,k.ordinal,k.byte_start,k.byte_end "
        "FROM chunks k JOIN documents d ON d.digest=k.doc_digest";
    std::string where;
    if (namespace_filter) where += " d.namespace=?1";
    if (authority_filter) {
        if (!where.empty()) where += " AND";
        where += namespace_filter ? " d.authority=?2" : " d.authority=?1";
    }
    if (!where.empty()) sql += " WHERE" + where;
    sql += " ORDER BY k.digest ASC LIMIT ?3 OFFSET ?4;";

    Stmt s;
    if (prepare(c, s, sql.c_str()) != 0) return -1;
    int idx = 1;
    if (namespace_filter) sqlite3_bind_text(s.p, idx++, namespace_filter, -1, SQLITE_STATIC);
    if (authority_filter) sqlite3_bind_text(s.p, idx++, authority_filter, -1, SQLITE_STATIC);
    sqlite3_bind_int64(s.p, 3, (sqlite3_int64)limit);
    sqlite3_bind_int64(s.p, 4, (sqlite3_int64)offset);

    uint32_t n = 0;
    for (;;) {
        int rc = sqlite3_step(s.p);
        if (rc == SQLITE_DONE) break;
        if (rc != SQLITE_ROW) { set_sql_error(c, "list_chunks"); return -1; }
        if (n >= limit) break;
        elpis_chunk_ref &r = out[n];
        std::memset(&r, 0, sizeof r);
        std::snprintf(r.chunk_digest, sizeof r.chunk_digest, "%s", (const char *)sqlite3_column_text(s.p, 0));
        std::snprintf(r.doc_digest, sizeof r.doc_digest, "%s", (const char *)sqlite3_column_text(s.p, 1));
        std::snprintf(r.ns, sizeof r.ns, "%s", (const char *)sqlite3_column_text(s.p, 2));
        std::snprintf(r.authority, sizeof r.authority, "%s", (const char *)sqlite3_column_text(s.p, 3));
        r.ordinal = (uint64_t)sqlite3_column_int64(s.p, 4);
        r.byte_start = (uint64_t)sqlite3_column_int64(s.p, 5);
        r.byte_end = (uint64_t)sqlite3_column_int64(s.p, 6);
        ++n;
    }
    *n_out = n;
    return 0;
}

/* The implementation builds a std::string SQL statement; no C++ exception may
 * cross this C ABI boundary. */
int elpis_corpus_list_chunks(elpis_corpus *c, const char *namespace_filter,
                             const char *authority_filter, uint64_t offset,
                             uint32_t limit, elpis_chunk_ref *out, uint32_t *n_out) {
    try {
        return list_chunks_impl(c, namespace_filter, authority_filter, offset, limit, out, n_out);
    } catch (...) {
        set_error(c, "list_chunks: internal allocation failure");
        return -1;
    }
}

static int corpus_chunk_lookup_impl(elpis_corpus *c, const char *digest, elpis_chunk_ref *out) {
    if (!c || !out || !valid_hex64(digest)) return -1;
    Stmt s;
    if (prepare(c, s,
        "SELECT c.digest,c.doc_digest,d.namespace,d.authority,c.ordinal,c.byte_start,c.byte_end "
        "FROM chunks c JOIN documents d ON d.digest=c.doc_digest WHERE c.digest=?1;") != 0) return -1;
    sqlite3_bind_text(s.p, 1, digest, -1, SQLITE_STATIC);
    int rc = sqlite3_step(s.p);
    if (rc != SQLITE_ROW) {
        if (rc != SQLITE_DONE) set_sql_error(c, "chunk lookup");
        else set_error(c, "chunk not found");
        return -1;
    }
    std::memset(out, 0, sizeof *out);
    std::snprintf(out->chunk_digest, sizeof out->chunk_digest, "%s",
                  (const char *)sqlite3_column_text(s.p, 0));
    std::snprintf(out->doc_digest, sizeof out->doc_digest, "%s",
                  (const char *)sqlite3_column_text(s.p, 1));
    std::snprintf(out->ns, sizeof out->ns, "%s",
                  (const char *)sqlite3_column_text(s.p, 2));
    std::snprintf(out->authority, sizeof out->authority, "%s",
                  (const char *)sqlite3_column_text(s.p, 3));
    out->ordinal = (uint64_t)sqlite3_column_int64(s.p, 4);
    out->byte_start = (uint64_t)sqlite3_column_int64(s.p, 5);
    out->byte_end = (uint64_t)sqlite3_column_int64(s.p, 6);
    return 0;
}

int elpis_corpus_chunk_lookup(elpis_corpus *c, const char *digest, elpis_chunk_ref *out) {
    try {
        return corpus_chunk_lookup_impl(c, digest, out);
    } catch (...) {
        return -1;
    }
}

int elpis_corpus_manifest_json(elpis_corpus *c, char **out, char digest[65]) {
    if (!c || !out || !digest) return -1;
    *out = nullptr;
    uint64_t docs=0,chunks=0;if(elpis_corpus_counts(c,&docs,&chunks)!=0)return -1;
    std::string j="{\"chunk_count\":"+std::to_string(chunks)+",\"documents\":[";
    Stmt s;if(prepare(c,s,
      "SELECT d.authority,(SELECT count(*) FROM chunks c WHERE c.doc_digest=d.digest),d.digest,d.media_type,d.namespace,d.origin,d.bytes,d.chunk_profile_digest "
      "FROM documents d ORDER BY d.digest;")!=0)return -1;
    bool first=true;
    for(;;){int rc=sqlite3_step(s.p);if(rc==SQLITE_DONE)break;if(rc!=SQLITE_ROW)return -1;
        if (!first) j.push_back(',');
        first = false;
        j += "{\"authority\":";
        j+=json_escape(sqlite3_column_text(s.p,0),(size_t)sqlite3_column_bytes(s.p,0));
        j+=",\"chunk_count\":"+std::to_string(sqlite3_column_int64(s.p,1));j+=",\"chunk_profile_digest\":";
        j+=json_escape(sqlite3_column_text(s.p,7),(size_t)sqlite3_column_bytes(s.p,7));j+=",\"digest\":";
        j+=json_escape(sqlite3_column_text(s.p,2),(size_t)sqlite3_column_bytes(s.p,2));j+=",\"media_type\":";
        j+=json_escape(sqlite3_column_text(s.p,3),(size_t)sqlite3_column_bytes(s.p,3));j+=",\"namespace\":";
        j+=json_escape(sqlite3_column_text(s.p,4),(size_t)sqlite3_column_bytes(s.p,4));j+=",\"origin\":";
        j+=json_escape(sqlite3_column_text(s.p,5),(size_t)sqlite3_column_bytes(s.p,5));j+=",\"size_bytes\":"+std::to_string(sqlite3_column_int64(s.p,6))+"}";
    }
    j+="]";j+=",\"document_count\":"+std::to_string(docs)+",\"schema\":\"elpis-corpus-manifest-v1\"}";
    uint8_t dg[32];elpis_sha256(j.data(),j.size(),dg);elpis_hex32(dg,digest);
    char *p=(char *)std::malloc(j.size()+1);if(!p)return -1;std::memcpy(p,j.data(),j.size());p[j.size()]=0;*out=p;return 0;
}

int elpis_corpus_manifest_write(elpis_corpus *c, const char *path, char digest[65]) {
    if (!c || !path || !*path || !digest) return -1;
    char *j = nullptr;
    if (elpis_corpus_manifest_json(c, &j, digest) != 0) return -1;
    size_t n=std::strlen(j);int fd=::open(path,O_WRONLY|O_CREAT|O_EXCL,0444);if(fd<0){std::free(j);return -1;}
    int rc=(write_all(fd,j,n)==0&&::fsync(fd)==0&&::close(fd)==0&&fsync_parent(path)==0)?0:-1;
    if(rc!=0){::close(fd);::unlink(path);}std::free(j);return rc;
}

void elpis_free(void *p){std::free(p);}

} // extern C
