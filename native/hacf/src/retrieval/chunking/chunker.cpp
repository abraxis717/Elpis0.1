#include "elpis/chunking.h"
#include "elpis/sha256.h"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace {
struct Unit { size_t start, end; };

bool is_utf8_cont(unsigned char c) { return (c & 0xc0u) == 0x80u; }

size_t snap_backward(const unsigned char *b, size_t floor, size_t pos) {
    while (pos > floor && is_utf8_cont(b[pos])) --pos;
    return pos;
}

void push_unit(std::vector<Unit> &v, size_t s, size_t e) {
    if (e > s) v.push_back({s, e});
}

bool blank_range(const unsigned char *b, size_t s, size_t e) {
    for (size_t i = s; i < e; ++i)
        if (b[i] != ' ' && b[i] != '\t' && b[i] != '\r' && b[i] != '\n') return false;
    return true;
}

void trim_bounds(const unsigned char *b, size_t &s, size_t &e) {
    while (s < e && (b[s] == ' ' || b[s] == '\t' || b[s] == '\r' || b[s] == '\n')) ++s;
    while (e > s && (b[e-1] == ' ' || b[e-1] == '\t' || b[e-1] == '\r' || b[e-1] == '\n')) --e;
}

void split_text(const unsigned char *b, size_t len, bool markdown, std::vector<Unit> &out) {
    size_t start = 0, i = 0;
    while (i < len) {
        size_t line_start = i;
        while (i < len && b[i] != '\n') ++i;
        size_t line_end = i;
        if (i < len) ++i;
        bool blank = blank_range(b, line_start, line_end);
        bool heading = markdown && line_end > line_start && b[line_start] == '#';
        if (heading && line_start > start) { push_unit(out, start, line_start); start = line_start; }
        if (blank) { push_unit(out, start, line_end); start = i; }
    }
    push_unit(out, start, len);
}

void split_jsonl(const unsigned char *b, size_t len, std::vector<Unit> &out) {
    size_t i = 0;
    while (i < len) {
        size_t s = i;
        while (i < len && b[i] != '\n') ++i;
        size_t e = i;
        if (i < len) ++i;
        trim_bounds(b, s, e);
        push_unit(out, s, e);
    }
}

/* Split every top-level array element, including primitives. The scanner is
 * string/escape aware and treats nested arrays/objects as one element. */
void split_json(const unsigned char *b, size_t len, std::vector<Unit> &out) {
    size_t p = 0;
    while (p < len && (b[p]==' ' || b[p]=='\t' || b[p]=='\r' || b[p]=='\n')) ++p;
    if (p >= len || b[p] != '[') { push_unit(out, 0, len); return; }
    ++p;
    size_t elem = p;
    unsigned depth = 1;
    bool in_str = false, esc = false;
    for (; p < len; ++p) {
        unsigned char c = b[p];
        if (in_str) {
            if (esc) esc = false;
            else if (c == '\\') esc = true;
            else if (c == '"') in_str = false;
            continue;
        }
        if (c == '"') { in_str = true; continue; }
        if (c == '[' || c == '{') { ++depth; continue; }
        if (c == ']' || c == '}') {
            if (depth == 1 && c == ']') {
                size_t s = elem, e = p; trim_bounds(b, s, e); push_unit(out, s, e);
                return;
            }
            if (depth > 1) --depth;
            continue;
        }
        if (c == ',' && depth == 1) {
            size_t s = elem, e = p; trim_bounds(b, s, e); push_unit(out, s, e);
            elem = p + 1;
        }
    }
    out.clear();
    push_unit(out, 0, len); /* malformed JSON is preserved as one deterministic unit */
}

void split_code(const unsigned char *b, size_t len, std::vector<Unit> &out) {
    size_t start = 0, i = 0;
    long depth = 0;
    bool in_str=false, in_chr=false, in_line=false, in_block=false, esc=false;
    while (i < len) {
        size_t ls = i;
        while (i < len && b[i] != '\n') ++i;
        size_t le = i;
        if (i < len) ++i;
        bool blank = blank_range(b, ls, le);
        for (size_t k = ls; k < le; ++k) {
            unsigned char c = b[k];
            if (in_line) continue;
            if (in_block) { if (c == '/' && k > ls && b[k-1] == '*') in_block=false; continue; }
            if (in_str) { if (esc) esc=false; else if (c=='\\') esc=true; else if (c=='"') in_str=false; continue; }
            if (in_chr) { if (esc) esc=false; else if (c=='\\') esc=true; else if (c=='\'') in_chr=false; continue; }
            if (c=='"') { in_str=true; continue; }
            if (c=='\'') { in_chr=true; continue; }
            if (c=='/' && k+1<le && b[k+1]=='/') { in_line=true; continue; }
            if (c=='/' && k+1<le && b[k+1]=='*') { in_block=true; continue; }
            if (c=='{') ++depth;
            else if (c=='}' && depth>0) --depth;
        }
        in_line=false;
        if (blank && depth==0) { push_unit(out, start, le); start=i; }
    }
    push_unit(out, start, len);
}

void hash_string(const std::string &s, char out[65]) {
    uint8_t d[32]; elpis_sha256(s.data(), s.size(), d); elpis_hex32(d, out);
}

void append_u32(std::string &s, uint32_t v) {
    s.push_back((char)(v>>24)); s.push_back((char)(v>>16)); s.push_back((char)(v>>8)); s.push_back((char)v);
}
void append_field(std::string &s, const char *p, size_t n) {
    append_u32(s, (uint32_t)n); s.append(p, n);
}
}

extern "C" {

void elpis_chunk_profile_default(elpis_chunk_profile *p) {
    if (!p) return;
    std::memset(p, 0, sizeof *p);
    std::memcpy(p->name, "structural-v1", sizeof("structural-v1"));
    p->target_bytes=2048; p->max_bytes=4096; p->min_bytes=256; p->version=1;
}

int elpis_chunk_profile_validate(const elpis_chunk_profile *p) {
    if (!p) return -1;
    if (!std::memchr(p->name, '\0', sizeof p->name)) return -1;
    if (p->name[0] == '\0' || p->version == 0) return -1;
    if (p->target_bytes == 0 || p->max_bytes == 0) return -1;
    if (p->target_bytes > p->max_bytes || p->min_bytes > p->target_bytes) return -1;
    return 0;
}

int elpis_chunk_profile_digest_checked(const elpis_chunk_profile *p, const char *media_type, char out[65]) {
    if (!out || elpis_chunk_profile_validate(p) != 0) return -1;
    const char *mt = media_type ? media_type : "";
    size_t mt_len = std::strlen(mt);
    if (mt_len > UINT32_MAX) return -1;
    std::string canon("elpis-chunk-profile-v1");
    append_field(canon, p->name, std::strlen(p->name));
    append_u32(canon, p->version); append_u32(canon, p->target_bytes);
    append_u32(canon, p->max_bytes); append_u32(canon, p->min_bytes);
    append_field(canon, mt, mt_len);
    hash_string(canon, out);
    return 0;
}

void elpis_chunk_profile_digest(const elpis_chunk_profile *p, const char *media_type, char out[65]) {
    if (elpis_chunk_profile_digest_checked(p, media_type, out) != 0 && out) out[0] = '\0';
}

size_t elpis_normalize(const char *in, size_t len, char *out, size_t out_cap) {
    if (!in && len) return 0;
    std::string tmp; tmp.reserve(len);
    size_t line_start=0;
    for (size_t i=0; i<=len; ++i) {
        if (i==len || in[i]=='\n') {
            size_t e=i;
            while (e>line_start && (in[e-1]==' ' || in[e-1]=='\t' || in[e-1]=='\r')) --e;
            if (e>line_start) tmp.append(in+line_start, e-line_start);
            if (i<len) tmp.push_back('\n');
            line_start=i+1;
        }
    }
    while (!tmp.empty() && tmp.back()=='\n') tmp.pop_back();
    if (out && out_cap) {
        size_t n=std::min(tmp.size(), out_cap-1);
        if (n) std::memcpy(out, tmp.data(), n);
        out[n]='\0';
    }
    return tmp.size();
}

int elpis_chunk_document(const void *bytes, size_t len, const char *media_type,
                         const elpis_chunk_profile *p, const char *doc_digest,
                         elpis_chunk **out, size_t *n_out) {
    if ((!bytes && len) || !p || !doc_digest || !out || !n_out) return -1;
    *out=nullptr; *n_out=0;
    if (elpis_chunk_profile_validate(p) != 0) return -1;
    const unsigned char *b=(const unsigned char *)bytes;
    const char *mt=media_type ? media_type : ELPIS_MT_TEXT;
    char profile_digest[65];
    if (elpis_chunk_profile_digest_checked(p, mt, profile_digest) != 0) return -1;

    std::vector<Unit> units;
    if (!std::strcmp(mt, ELPIS_MT_MARKDOWN)) split_text(b,len,true,units);
    else if (!std::strcmp(mt, ELPIS_MT_JSONL)) split_jsonl(b,len,units);
    else if (!std::strcmp(mt, ELPIS_MT_JSON)) split_json(b,len,units);
    else if (!std::strcmp(mt, ELPIS_MT_CODE)) split_code(b,len,units);
    else split_text(b,len,false,units);

    std::vector<Unit> sized;
    for (const Unit &u: units) {
        size_t s=u.start;
        while (u.end-s > p->max_bytes) {
            size_t desired=s+std::min((size_t)p->target_bytes,(size_t)p->max_bytes);
            size_t cut=snap_backward(b,s,desired);
            if (cut<=s) cut=std::min(u.end,s+(size_t)p->max_bytes);
            if (cut<=s || cut>=u.end) return -1;
            sized.push_back({s,cut}); s=cut;
        }
        push_unit(sized,s,u.end);
    }

    std::vector<Unit> packed;
    const bool preserve_structural_units = std::strcmp(mt, ELPIS_MT_TEXT) != 0;
    for (const Unit &u: sized) {
        if (!preserve_structural_units && !packed.empty()) {
            Unit &last=packed.back();
            size_t merged=u.end-last.start;
            if (merged<=p->target_bytes &&
                (last.end-last.start<p->min_bytes || u.end-u.start<p->min_bytes)) {
                last.end=u.end; continue;
            }
        }
        packed.push_back(u);
    }
    for (const Unit &u: packed) if (u.end-u.start > p->max_bytes) return -1;
    if (packed.empty()) return 0;

    elpis_chunk *arr=(elpis_chunk *)std::calloc(packed.size(),sizeof *arr);
    if (!arr) return -1;
    for (size_t i=0;i<packed.size();++i) {
        Unit u=packed[i];
        arr[i].ordinal=i; arr[i].byte_start=u.start; arr[i].byte_end=u.end;
        size_t nn=elpis_normalize((const char *)b+u.start,u.end-u.start,nullptr,0);
        std::vector<char> norm_buf(nn + 1);
        elpis_normalize((const char *)b+u.start,u.end-u.start,norm_buf.data(),norm_buf.size());
        std::string norm(norm_buf.data(), nn);
        hash_string(norm,arr[i].norm_digest);
        std::string id("elpis-chunk-v1");
        append_field(id,doc_digest,std::strlen(doc_digest)); append_u32(id,(uint32_t)i);
        append_u32(id,(uint32_t)(u.start>>32)); append_u32(id,(uint32_t)u.start);
        append_u32(id,(uint32_t)(u.end>>32)); append_u32(id,(uint32_t)u.end);
        append_field(id,arr[i].norm_digest,64); append_field(id,profile_digest,64);
        hash_string(id,arr[i].digest);
    }
    *out=arr; *n_out=packed.size(); return 0;
}

void elpis_chunks_free(elpis_chunk *chunks) { std::free(chunks); }
}
