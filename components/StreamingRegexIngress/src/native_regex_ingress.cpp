#define PCRE2_CODE_UNIT_WIDTH 8
#include <pcre2.h>

#include "elpis/sha256.h"

#include <algorithm>
#include <array>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <variant>
#include <vector>

static constexpr size_t DEFAULT_CARRY_BYTES = 1024u;
static constexpr const char *SCHEMA = "elpis.regex-lexical-evidence.v1";
static constexpr const char *CANDIDATE_SCHEMA = "elpis.regex-task-candidate.v1";

struct JsonNumber { std::string text; };

struct J {
    using A = std::vector<J>;
    using O = std::map<std::string,J>;
    std::variant<std::nullptr_t,bool,JsonNumber,std::string,A,O> v;

    J():v(nullptr){}
    J(std::nullptr_t):v(nullptr){}
    J(bool x):v(x){}
    J(const char *s):v(std::string(s)){}
    J(std::string s):v(std::move(s)){}
    J(A a):v(std::move(a)){}
    J(O o):v(std::move(o)){}
    static J num(std::string s){ J x; x.v=JsonNumber{std::move(s)}; return x; }

    const O &obj() const { return std::get<O>(v); }
    const A &arr() const { return std::get<A>(v); }
};

static void json_escape_append(std::string &out, const std::string &s) {
    out.push_back('"');
    static const char hex[]="0123456789abcdef";
    for (unsigned char c : s) {
        switch(c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) {
                    out += "\\u00";
                    out.push_back(hex[c >> 4]);
                    out.push_back(hex[c & 15]);
                } else {
                    out.push_back((char)c);
                }
        }
    }
    out.push_back('"');
}

static void dump_into(const J &j, std::string &out) {
    if (std::holds_alternative<std::nullptr_t>(j.v)) { out += "null"; return; }
    if (auto p=std::get_if<bool>(&j.v)) { out += *p ? "true" : "false"; return; }
    if (auto p=std::get_if<JsonNumber>(&j.v)) { out += p->text; return; }
    if (auto p=std::get_if<std::string>(&j.v)) { json_escape_append(out,*p); return; }
    if (auto p=std::get_if<J::A>(&j.v)) {
        out.push_back('[');
        for (size_t i=0;i<p->size();++i) {
            if(i) out.push_back(',');
            dump_into((*p)[i],out);
        }
        out.push_back(']');
        return;
    }
    const auto &o=std::get<J::O>(j.v);
    out.push_back('{');
    bool first=true;
    for (const auto &kv:o) {
        if(!first) out.push_back(',');
        first=false;
        json_escape_append(out,kv.first);
        out.push_back(':');
        dump_into(kv.second,out);
    }
    out.push_back('}');
}

static std::string dump(const J &j) {
    std::string out;
    dump_into(j,out);
    return out;
}

static std::string hex_digest(const uint8_t d[32]) {
    static const char h[]="0123456789abcdef";
    std::string out(64,'0');
    for(int i=0;i<32;++i) {
        out[2*i]=h[d[i]>>4];
        out[2*i+1]=h[d[i]&15];
    }
    return out;
}

static std::string sha_bytes(const void *p, size_t n) {
    uint8_t d[32];
    elpis_sha256(p,n,d);
    return hex_digest(d);
}
static std::string sha_string(const std::string &s) {
    return sha_bytes(s.data(),s.size());
}
static std::string sha_json(const J &j) {
    return sha_string(dump(j));
}

static std::string python_number(const std::string &text) {
    char *end=nullptr;
    double v=std::strtod(text.c_str(),&end);
    if(!end || *end!='\0' || !std::isfinite(v))
        throw std::runtime_error("NUMBER_PARSE");

    if (std::trunc(v)==v) {
        if (v==0.0) return "0";
        std::ostringstream oss;
        oss.setf(std::ios::fixed,std::ios::floatfield);
        oss << std::setprecision(0) << v;
        return oss.str();
    }
    char buf[128];
    auto r=std::to_chars(buf,buf+sizeof(buf),v,std::chars_format::general);
    if(r.ec!=std::errc()) throw std::runtime_error("NUMBER_FORMAT");
    return std::string(buf,r.ptr);
}

enum class PK {
    CMP_GTE, CMP_GT, CMP_LTE, CMP_LT, CMP_NE, CMP_EQ,
    BOUNDS, ROLE_LOWER, ROLE_UPPER,
    COAL_STRICT_NEG, COAL_STRICT_POS, COAL_TOUCH,
    REDUCER_MAX, REDUCER_MIN
};

struct Pattern {
    const char *id;
    const char *kind;
    const char *expr;
    const char *anchor;
    PK payload_kind;
    pcre2_code *code=nullptr;
    int scalar_group=0, value_group=0, lower_group=0, upper_group=0, subject_group=0;
};

static std::vector<Pattern> patterns() {
    return {
      {"cmp.gte.at_least.v1","comparison",
       R"(\b(?:at\s+least|no\s+less\s+than|greater\s+than\s+or\s+equal\s+to)\s+(?<scalar>[-+]?(?:\d{1,32}(?:\.\d{0,16})?|\.\d{1,16}))\b)",
       "at least",PK::CMP_GTE},
      {"cmp.gt.more_than.v1","comparison",
       R"(\b(?:more\s+than|greater\s+than|strictly\s+greater\s+than|above)\s+(?<scalar>[-+]?(?:\d{1,32}(?:\.\d{0,16})?|\.\d{1,16}))\b)",
       "greater than",PK::CMP_GT},
      {"cmp.lte.at_most.v1","comparison",
       R"(\b(?:at\s+most|no\s+greater\s+than|less\s+than\s+or\s+equal\s+to)\s+(?<scalar>[-+]?(?:\d{1,32}(?:\.\d{0,16})?|\.\d{1,16}))\b)",
       "at most",PK::CMP_LTE},
      {"cmp.lt.less_than.v1","comparison",
       R"(\b(?:less\s+than|strictly\s+less\s+than|below)\s+(?<scalar>[-+]?(?:\d{1,32}(?:\.\d{0,16})?|\.\d{1,16}))\b)",
       "less than",PK::CMP_LT},
      {"cmp.ne.other_than.v1","comparison",
       R"(\b(?:other\s+than|not\s+equal\s+to|unequal\s+to)\s+(?<scalar>[-+]?(?:\d{1,32}(?:\.\d{0,16})?|\.\d{1,16}))\b)",
       "not equal",PK::CMP_NE},
      {"cmp.eq.exact.v1","comparison",
       R"(\b(?:exactly\s+equal\s+to|equal\s+to|exactly)\s+(?<scalar>[-+]?(?:\d{1,32}(?:\.\d{0,16})?|\.\d{1,16}))\b)",
       "equal to",PK::CMP_EQ},
      {"bounds.direct.v1","bounds",
       R"(\b(?:clamp|bound|restrict|keep)\s+(?<value>[A-Za-z_][A-Za-z0-9_]{0,127})\s+(?:between|from)\s+(?<lower>[A-Za-z_][A-Za-z0-9_]{0,127})\s+(?:and|through|to)\s+(?<upper>[A-Za-z_][A-Za-z0-9_]{0,127})\b)",
       "lower bound",PK::BOUNDS},
      {"role.lower.explicit.v1","role_binding",
       R"(\b(?<subject>[A-Za-z_][A-Za-z0-9_]{0,127})\s+(?:is|as)\s+(?:the\s+)?(?:lower\s+(?:bound|limit)|minimum|floor)\b)",
       "lower bound",PK::ROLE_LOWER},
      {"role.upper.explicit.v1","role_binding",
       R"(\b(?<subject>[A-Za-z_][A-Za-z0-9_]{0,127})\s+(?:is|as)\s+(?:the\s+)?(?:upper\s+(?:bound|limit)|maximum|ceiling)\b)",
       "upper bound",PK::ROLE_UPPER},
      {"coal.strict.negated_touch.v1","coalescence_relation",
       R"(\b(?:touch(?:ing)?\s+(?:endpoints?|boundaries)|endpoint\s+contact)(?:\s+[\w-]{1,64}){0,5}\s+(?:do\s+not|does\s+not|don't|doesn't)\s+merge\b)",
       "touching endpoints",PK::COAL_STRICT_NEG},
      {"coal.strict.positive_width.v1","coalescence_relation",
       R"(\b(?:strict(?:ly)?\s+overlap(?:ping)?|positive[-\s]width\s+overlap|interiors?\s+overlap)\b)",
       "strict overlap",PK::COAL_STRICT_POS},
      {"coal.touching.allowed.v1","coalescence_relation",
       R"(\b(?:overlap(?:ping)?\s+or\s+(?:touch(?:ing)?|abut(?:ting)?)(?:\s+(?:intervals?|ranges?|endpoints?|boundaries))?|(?:touch(?:ing)?|abut(?:ting)?)\s+(?:endpoints?|boundaries|ranges?|intervals?))\s+(?:(?:may|can|do|should|must|will)\s+)?(?:also\s+)?merge\b)",
       "touching endpoints",PK::COAL_TOUCH},
      {"coal.reducer.max.v1","coalescence_reducer",
       R"(\b(?:maximum|max|greatest|farthest|farther|larger)\s+(?:end|endpoint|ending\s+coordinate|right\s+edge)\b)",
       "maximum end",PK::REDUCER_MAX},
      {"coal.reducer.min.v1","coalescence_reducer",
       R"(\b(?:minimum|min|smallest|nearest|nearer|lesser)\s+(?:end|endpoint|ending\s+coordinate|right\s+edge)\b)",
       "minimum end",PK::REDUCER_MIN}
    };
}

static int group_num(pcre2_code *code, const char *name) {
    int n=pcre2_substring_number_from_name(code,(PCRE2_SPTR)name);
    return n<0?0:n;
}

static void compile_patterns(std::vector<Pattern> &ps) {
    for(auto &p:ps) {
        int err=0; PCRE2_SIZE off=0;
        p.code=pcre2_compile(
            (PCRE2_SPTR)p.expr,
            PCRE2_ZERO_TERMINATED,
            PCRE2_UTF|PCRE2_UCP|PCRE2_CASELESS,
            &err,&off,nullptr);
        if(!p.code) {
            PCRE2_UCHAR msg[256];
            pcre2_get_error_message(err,msg,sizeof(msg));
            throw std::runtime_error(
                std::string("PCRE2_COMPILE:")+p.id+":"+std::to_string((size_t)off)+":"+(char*)msg);
        }
        p.scalar_group=group_num(p.code,"scalar");
        p.value_group=group_num(p.code,"value");
        p.lower_group=group_num(p.code,"lower");
        p.upper_group=group_num(p.code,"upper");
        p.subject_group=group_num(p.code,"subject");
    }
}
static void free_patterns(std::vector<Pattern> &ps) {
    for(auto &p:ps) if(p.code) pcre2_code_free(p.code);
}

static std::string cap(
    const std::string &subject,
    PCRE2_SIZE *ov,
    int group)
{
    if(group<=0) throw std::runtime_error("CAPTURE_GROUP_MISSING");
    PCRE2_SIZE a=ov[2*group], b=ov[2*group+1];
    if(a==PCRE2_UNSET || b==PCRE2_UNSET || b<a || b>subject.size())
        throw std::runtime_error("CAPTURE_UNSET");
    return subject.substr((size_t)a,(size_t)(b-a));
}

static J payload_for(const Pattern &p,const std::string &subject,PCRE2_SIZE *ov) {
    J::O o;
    switch(p.payload_kind) {
        case PK::CMP_GTE: case PK::CMP_GT: case PK::CMP_LTE:
        case PK::CMP_LT: case PK::CMP_NE: case PK::CMP_EQ: {
            const char *op =
                p.payload_kind==PK::CMP_GTE?">=":
                p.payload_kind==PK::CMP_GT?">":
                p.payload_kind==PK::CMP_LTE?"<=":
                p.payload_kind==PK::CMP_LT?"<":
                p.payload_kind==PK::CMP_NE?"!=":"==";
            o["kind"]="comparison";
            o["operator"]=op;
            o["scalar"]=J::num(python_number(cap(subject,ov,p.scalar_group)));
            break;
        }
        case PK::BOUNDS:
            o["kind"]="bounds";
            o["lower"]=cap(subject,ov,p.lower_group);
            o["upper"]=cap(subject,ov,p.upper_group);
            o["value"]=cap(subject,ov,p.value_group);
            break;
        case PK::ROLE_LOWER:
            o["kind"]="role_binding"; o["role"]="lower";
            o["subject"]=cap(subject,ov,p.subject_group); break;
        case PK::ROLE_UPPER:
            o["kind"]="role_binding"; o["role"]="upper";
            o["subject"]=cap(subject,ov,p.subject_group); break;
        case PK::COAL_STRICT_NEG:
            o["kind"]="coalescence_relation"; o["negated"]=true;
            o["relation"]="strict_overlap"; o["touching_allowed"]=false; break;
        case PK::COAL_STRICT_POS:
            o["kind"]="coalescence_relation"; o["negated"]=false;
            o["relation"]="strict_overlap"; o["touching_allowed"]=false; break;
        case PK::COAL_TOUCH:
            o["kind"]="coalescence_relation"; o["negated"]=false;
            o["relation"]="touching_or_overlap"; o["touching_allowed"]=true; break;
        case PK::REDUCER_MAX:
            o["kind"]="coalescence_reducer"; o["reducer"]="max"; break;
        case PK::REDUCER_MIN:
            o["kind"]="coalescence_reducer"; o["reducer"]="min"; break;
    }
    return J(std::move(o));
}

struct Evidence {
    std::string pattern_id, evidence_kind, lexical_anchor;
    uint64_t start_byte=0,end_byte=0;
    std::string matched_text, matched_sha;
    J payload;
};

struct Utf8Prefix {
    size_t complete=0;
    bool valid=true;
};

static Utf8Prefix utf8_complete_prefix(const std::string &s) {
    size_t i=0;
    auto cont=[&](size_t j){return j<s.size() && ((unsigned char)s[j]&0xC0)==0x80;};
    while(i<s.size()) {
        unsigned char c=(unsigned char)s[i];
        if(c<0x80){++i;continue;}
        size_t need=0;
        if(c>=0xC2 && c<=0xDF) need=2;
        else if(c>=0xE0 && c<=0xEF) need=3;
        else if(c>=0xF0 && c<=0xF4) need=4;
        else return {i,false};
        if(i+need>s.size()) return {i,true};
        for(size_t k=1;k<need;++k) if(!cont(i+k)) return {i,false};
        if(need==3) {
            unsigned char c1=(unsigned char)s[i+1];
            if(c==0xE0 && c1<0xA0) return {i,false};
            if(c==0xED && c1>=0xA0) return {i,false};
        } else if(need==4) {
            unsigned char c1=(unsigned char)s[i+1];
            if(c==0xF0 && c1<0x90) return {i,false};
            if(c==0xF4 && c1>=0x90) return {i,false};
        }
        i+=need;
    }
    return {s.size(),true};
}

static std::string safe_carry(const std::string &data,size_t max_bytes) {
    if(data.size()<=max_bytes) return data;
    size_t start=data.size()-max_bytes;
    while(start<data.size() && (((unsigned char)data[start]&0xC0)==0x80)) ++start;
    return data.substr(start);
}

static void scan_window(
    const std::string &window,
    uint64_t global_base,
    bool has_commit_end,
    uint64_t commit_end,
    std::vector<Pattern> &ps,
    std::vector<Evidence> &raw,
    std::set<std::tuple<std::string,uint64_t,uint64_t>> &seen)
{
    for(auto &p:ps) {
        pcre2_match_data *md=pcre2_match_data_create_from_pattern(p.code,nullptr);
        if(!md) throw std::runtime_error("PCRE2_MATCH_DATA");
        PCRE2_SIZE offset=0;
        while(offset<=window.size()) {
            int rc=pcre2_match(
                p.code,
                (PCRE2_SPTR)window.data(),
                window.size(),
                offset,
                0,
                md,
                nullptr);
            if(rc==PCRE2_ERROR_NOMATCH) break;
            if(rc<0) {
                pcre2_match_data_free(md);
                throw std::runtime_error(std::string("PCRE2_MATCH:")+p.id+":"+std::to_string(rc));
            }
            PCRE2_SIZE *ov=pcre2_get_ovector_pointer(md);
            size_t a=(size_t)ov[0], b=(size_t)ov[1];
            if(b<a || b>window.size()) {
                pcre2_match_data_free(md);
                throw std::runtime_error("PCRE2_OVECTOR");
            }
            uint64_t ga=global_base+a, gb=global_base+b;
            if(!has_commit_end || gb<=commit_end) {
                auto key=std::make_tuple(std::string(p.id),ga,gb);
                if(seen.insert(key).second) {
                    std::string matched=window.substr(a,b-a);
                    raw.push_back(Evidence{
                        p.id,p.kind,p.anchor,ga,gb,matched,sha_string(matched),
                        payload_for(p,window,ov)
                    });
                }
            }
            if(b>a) offset=b;
            else {
                if(b>=window.size()) break;
                offset=b+1;
            }
        }
        pcre2_match_data_free(md);
    }
}

static J evidence_to_json(const Evidence &e,const std::string &source_sha) {
    J::O bound;
    bound["admission_authority"]=false;
    bound["candidate_status"]="PROPOSED_UNADMITTED";
    bound["end_byte"]=J::num(std::to_string(e.end_byte));
    bound["evidence_kind"]=e.evidence_kind;
    bound["execution_authority"]=false;
    bound["lexical_anchor"]=e.lexical_anchor;
    bound["matched_text"]=e.matched_text;
    bound["matched_text_sha256"]=e.matched_sha;
    bound["pattern_id"]=e.pattern_id;
    bound["payload"]=e.payload;
    bound["runtime_admission"]=false;
    bound["schema"]=SCHEMA;
    bound["semantic_authority"]=false;
    bound["source_sha256"]=source_sha;
    bound["start_byte"]=J::num(std::to_string(e.start_byte));
    std::string eid=sha_json(J(bound));
    bound["evidence_id"]=eid;
    return J(std::move(bound));
}

static std::string get_s(const J::O &o,const char *key) {
    return std::get<std::string>(o.at(key).v);
}
static bool get_b(const J::O &o,const char *key) {
    return std::get<bool>(o.at(key).v);
}
static std::string get_n(const J::O &o,const char *key) {
    return std::get<JsonNumber>(o.at(key).v).text;
}

static J compose(const std::vector<J> &evidence,const std::string &source_sha) {
    std::set<std::pair<std::string,std::string>> comparisons;
    std::set<std::tuple<std::string,std::string,std::string>> bounds;
    std::set<std::pair<std::string,bool>> relations;
    std::set<std::string> reducers;
    std::map<std::string,std::set<std::string>> roles;

    for(const J &ej:evidence) {
        const auto &eo=ej.obj();
        const auto &po=eo.at("payload").obj();
        std::string kind=get_s(po,"kind");
        if(kind=="comparison") comparisons.emplace(get_s(po,"operator"),get_n(po,"scalar"));
        else if(kind=="bounds") bounds.emplace(get_s(po,"value"),get_s(po,"lower"),get_s(po,"upper"));
        else if(kind=="coalescence_relation") relations.emplace(get_s(po,"relation"),get_b(po,"touching_allowed"));
        else if(kind=="coalescence_reducer") reducers.insert(get_s(po,"reducer"));
        else if(kind=="role_binding") roles[get_s(po,"role")].insert(get_s(po,"subject"));
    }

    J::A ambiguity;
    std::vector<J> payload_candidates;

    if(comparisons.size()==1) {
        auto [op,num]=*comparisons.begin();
        payload_candidates.push_back(J(J::O{
            {"kind","comparison"},{"operator",op},{"scalar",J::num(num)}
        }));
    } else if(comparisons.size()>1) {
        std::vector<J> vals;
        for(auto &x:comparisons)
            vals.push_back(J(J::A{J(x.first),J::num(x.second)}));
        std::sort(vals.begin(),vals.end(),[](const J&a,const J&b){return dump(a)<dump(b);});
        ambiguity.push_back(J(J::O{{"axis","comparison"},{"values",J(J::A(vals))}}));
    }

    if(bounds.size()==1) {
        auto [value,lower,upper]=*bounds.begin();
        payload_candidates.push_back(J(J::O{
            {"kind","bounds"},{"lower",lower},{"upper",upper},{"value",value}
        }));
    } else if(bounds.size()>1) {
        std::vector<J> vals;
        for(auto &x:bounds) {
            vals.push_back(J(J::A{J(std::get<0>(x)),J(std::get<1>(x)),J(std::get<2>(x))}));
        }
        std::sort(vals.begin(),vals.end(),[](const J&a,const J&b){return dump(a)<dump(b);});
        ambiguity.push_back(J(J::O{{"axis","bounds"},{"values",J(J::A(vals))}}));
    }

    if(relations.size()>1) {
        std::vector<J> vals;
        for(auto &x:relations) vals.push_back(J(J::A{J(x.first),J(x.second)}));
        std::sort(vals.begin(),vals.end(),[](const J&a,const J&b){return dump(a)<dump(b);});
        ambiguity.push_back(J(J::O{{"axis","coalescence_relation"},{"values",J(J::A(vals))}}));
    }
    if(reducers.size()>1) {
        J::A vals;
        for(auto &x:reducers) vals.push_back(J(x));
        ambiguity.push_back(J(J::O{{"axis","coalescence_reducer"},{"values",J(std::move(vals))}}));
    }
    if(relations.size()==1 && reducers.size()==1) {
        auto rel=*relations.begin();
        payload_candidates.push_back(J(J::O{
            {"kind","coalescence"},
            {"reducer",*reducers.begin()},
            {"relation",rel.first},
            {"touching_allowed",rel.second}
        }));
    }

    for(const auto &rv:roles) {
        if(rv.second.size()==1) {
            payload_candidates.push_back(J(J::O{
                {"kind","role_binding"},{"role",rv.first},{"subject",*rv.second.begin()}
            }));
        } else {
            J::A vals;
            for(const auto &s:rv.second) vals.push_back(J(s));
            ambiguity.push_back(J(J::O{
                {"axis",std::string("role:")+rv.first},{"values",J(std::move(vals))}
            }));
        }
    }

    std::sort(payload_candidates.begin(),payload_candidates.end(),
              [](const J&a,const J&b){return dump(a)<dump(b);});

    J::A bound_candidates;
    for(const J &payload:payload_candidates) {
        J::O row;
        row["admission_authority"]=false;
        row["candidate_status"]="PROPOSED_UNADMITTED";
        row["execution_authority"]=false;
        row["payload"]=payload;
        row["runtime_admission"]=false;
        row["schema"]=CANDIDATE_SCHEMA;
        row["semantic_authority"]=false;
        row["source_sha256"]=source_sha;
        std::string cid=sha_json(J(row));
        row["candidate_id"]=cid;
        bound_candidates.push_back(J(std::move(row)));
    }

    J::O out;
    out["admission_authority"]=false;
    out["ambiguities"]=J(std::move(ambiguity));
    out["candidate_status"]="PROPOSED_UNADMITTED";
    out["candidates"]=J(std::move(bound_candidates));
    out["execution_authority"]=false;
    out["fail_closed"]=!std::get<J::A>(out["ambiguities"].v).empty();
    out["runtime_admission"]=false;
    out["schema"]="elpis.regex-task-composition.v1";
    out["semantic_authority"]=false;
    out["source_sha256"]=source_sha;
    return J(std::move(out));
}

static J parse_file(const std::string &path,size_t chunk_size,size_t carry_bytes) {
    if(chunk_size==0 || carry_bytes<256) throw std::runtime_error("INVALID_STREAM_BOUNDS");

    std::ifstream f(path,std::ios::binary);
    if(!f) throw std::runtime_error("INPUT_OPEN");

    auto ps=patterns();
    compile_patterns(ps);

    elpis_sha256_ctx source_ctx;
    elpis_sha256_init(&source_ctx);
    std::string carry;
    uint64_t total_before=0;
    std::vector<Evidence> raw;
    std::set<std::tuple<std::string,uint64_t,uint64_t>> seen;

    std::vector<char> buf(chunk_size);
    try {
        while(f) {
            f.read(buf.data(),(std::streamsize)buf.size());
            std::streamsize got=f.gcount();
            if(got<=0) break;
            std::string fresh(buf.data(),(size_t)got);
            elpis_sha256_update(&source_ctx,fresh.data(),fresh.size());

            std::string window=carry+fresh;
            uint64_t base=total_before-carry.size();
            uint64_t total_after=total_before+(uint64_t)fresh.size();

            Utf8Prefix up=utf8_complete_prefix(window);
            if(!up.valid) throw std::runtime_error("INVALID_UTF8");
            std::string complete=window.substr(0,up.complete);
            std::string suffix=window.substr(up.complete);

            uint64_t safe_commit_end=total_after>carry_bytes?total_after-carry_bytes:0u;
            scan_window(complete,base,true,safe_commit_end,ps,raw,seen);
            carry=safe_carry(complete+suffix,carry_bytes);
            total_before=total_after;
        }

        if(!carry.empty()) {
            Utf8Prefix up=utf8_complete_prefix(carry);
            if(!up.valid || up.complete!=carry.size()) throw std::runtime_error("INVALID_UTF8_EOF");
            scan_window(carry,total_before-carry.size(),false,0,ps,raw,seen);
        }
    } catch(...) {
        free_patterns(ps);
        throw;
    }
    free_patterns(ps);

    uint8_t source_digest_bytes[32];
    elpis_sha256_final(&source_ctx,source_digest_bytes);
    std::string source_sha=hex_digest(source_digest_bytes);

    std::sort(raw.begin(),raw.end(),[](const Evidence&a,const Evidence&b){
        if(a.start_byte!=b.start_byte) return a.start_byte<b.start_byte;
        if(a.end_byte!=b.end_byte) return a.end_byte<b.end_byte;
        return a.pattern_id<b.pattern_id;
    });

    J::A evidence;
    for(const auto &e:raw) evidence.push_back(evidence_to_json(e,source_sha));

    J::O ingress;
    ingress["admission_authority"]=false;
    ingress["candidate_status"]="PROPOSED_UNADMITTED";
    ingress["evidence"]=J(evidence);
    ingress["execution_authority"]=false;
    ingress["runtime_admission"]=false;
    ingress["schema"]="elpis.regex-stream-ingress-result.v1";
    ingress["semantic_authority"]=false;
    ingress["source_bytes"]=J::num(std::to_string(total_before));
    ingress["source_sha256"]=source_sha;

    J composition=compose(evidence,source_sha);

    J::O root;
    root["composition"]=composition;
    root["ingress"]=J(std::move(ingress));
    return J(std::move(root));
}

int main(int argc,char **argv) {
    try {
        std::string input;
        size_t chunk=4096,carry=DEFAULT_CARRY_BYTES;
        for(int i=1;i<argc;++i) {
            std::string a=argv[i];
            if(a=="--input" && i+1<argc) input=argv[++i];
            else if(a=="--chunk-size" && i+1<argc) chunk=(size_t)std::stoull(argv[++i]);
            else if(a=="--carry-bytes" && i+1<argc) carry=(size_t)std::stoull(argv[++i]);
            else throw std::runtime_error("USAGE");
        }
        if(input.empty()) throw std::runtime_error("USAGE");
        J result=parse_file(input,chunk,carry);
        std::cout << dump(result) << "\n";
        return 0;
    } catch(const std::exception &e) {
        std::cerr << "NATIVE_REGEX_FAIL:" << e.what() << "\n";
        return 2;
    }
}
