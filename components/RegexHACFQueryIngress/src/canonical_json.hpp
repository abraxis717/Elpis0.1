#ifndef ELPIS_REGEX_HACF_QUERY_INGRESS_CANONICAL_JSON_HPP
#define ELPIS_REGEX_HACF_QUERY_INGRESS_CANONICAL_JSON_HPP

#include "elpis/sha256.h"

#include <cstdint>
#include <map>
#include <string>
#include <variant>
#include <vector>

namespace elpis::regex_hacf_query_ingress::detail {

struct JsonNumber { std::string text; };
struct RawJson { std::string text; };

struct J {
    using A=std::vector<J>;
    using O=std::map<std::string,J>;
    std::variant<std::nullptr_t,bool,JsonNumber,RawJson,std::string,A,O> v;

    J():v(nullptr){}
    J(std::nullptr_t):v(nullptr){}
    J(bool x):v(x){}
    J(const char *s):v(std::string(s)){}
    J(std::string s):v(std::move(s)){}
    J(A a):v(std::move(a)){}
    J(O o):v(std::move(o)){}

    static J num(std::string s){ J x; x.v=JsonNumber{std::move(s)}; return x; }
    static J raw(std::string s){ J x; x.v=RawJson{std::move(s)}; return x; }

    const O &obj() const { return std::get<O>(v); }
    const A &arr() const { return std::get<A>(v); }
};

static inline void json_escape_append(std::string &out,const std::string &s) {
    out.push_back('"');
    static const char hex[]="0123456789abcdef";
    for(unsigned char c:s) {
        switch(c) {
            case '"': out+="\\\""; break;
            case '\\': out+="\\\\"; break;
            case '\b': out+="\\b"; break;
            case '\f': out+="\\f"; break;
            case '\n': out+="\\n"; break;
            case '\r': out+="\\r"; break;
            case '\t': out+="\\t"; break;
            default:
                if(c<0x20) {
                    out+="\\u00";
                    out.push_back(hex[c>>4]);
                    out.push_back(hex[c&15]);
                } else {
                    out.push_back((char)c);
                }
        }
    }
    out.push_back('"');
}

static inline void dump_into(const J &j,std::string &out) {
    if(std::holds_alternative<std::nullptr_t>(j.v)){out+="null";return;}
    if(auto p=std::get_if<bool>(&j.v)){out+=*p?"true":"false";return;}
    if(auto p=std::get_if<JsonNumber>(&j.v)){out+=p->text;return;}
    if(auto p=std::get_if<RawJson>(&j.v)){out+=p->text;return;}
    if(auto p=std::get_if<std::string>(&j.v)){json_escape_append(out,*p);return;}
    if(auto p=std::get_if<J::A>(&j.v)){
        out.push_back('[');
        for(size_t i=0;i<p->size();++i){
            if(i)out.push_back(',');
            dump_into((*p)[i],out);
        }
        out.push_back(']');
        return;
    }
    const auto &o=std::get<J::O>(j.v);
    out.push_back('{');
    bool first=true;
    for(const auto &kv:o){
        if(!first)out.push_back(',');
        first=false;
        json_escape_append(out,kv.first);
        out.push_back(':');
        dump_into(kv.second,out);
    }
    out.push_back('}');
}

static inline std::string dump(const J &j) {
    std::string out;
    dump_into(j,out);
    return out;
}

static inline std::string hex_digest(const uint8_t d[32]) {
    static const char h[]="0123456789abcdef";
    std::string out(64,'0');
    for(int i=0;i<32;++i){
        out[2*i]=h[d[i]>>4];
        out[2*i+1]=h[d[i]&15];
    }
    return out;
}

static inline std::string sha_string(const std::string &s) {
    uint8_t d[32];
    elpis_sha256(s.data(),s.size(),d);
    return hex_digest(d);
}

static inline std::string sha_json(const J &j) {
    return sha_string(dump(j));
}

} // namespace elpis::regex_hacf_query_ingress::detail

#endif
