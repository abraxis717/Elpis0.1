#define PCRE2_CODE_UNIT_WIDTH 8
#include <pcre2.h>
#include "incremental_lexer.h"
#include <algorithm>
#include <functional>
#include <map>
#include <stdexcept>
#include <utility>

namespace elpis_regex_v2 {
namespace {
std::string digest(elpis_sha256_ctx c) {
    uint8_t d[32]; elpis_sha256_final(&c,d);
    static const char h[]="0123456789abcdef";
    std::string s(64, '0');
    for(size_t i=0;i<32;++i) { s[2*i]=h[d[i]>>4]; s[2*i+1]=h[d[i]&15]; }
    return s;
}
using Code = std::shared_ptr<pcre2_code>;
using Data = std::unique_ptr<pcre2_match_data, decltype(&pcre2_match_data_free)>;
struct Predicate {
    Code code{nullptr, pcre2_code_free};
    Data data{nullptr, pcre2_match_data_free};
    std::array<bool,128> ascii{};
    bool current=false;
    Predicate(const Predicate& p):code(p.code),data(pcre2_match_data_create(1,nullptr),pcre2_match_data_free),ascii(p.ascii) {
        if(!data) throw std::bad_alloc();
    }
    Predicate(Predicate&&)=default;
    Predicate& operator=(Predicate&&)=default;
    explicit Predicate(const std::string& atom) {
        std::string expr="\\A(?:"+atom+")\\z";
        int error; PCRE2_SIZE offset;
        code.reset(pcre2_compile(reinterpret_cast<PCRE2_SPTR>(expr.data()), expr.size(),
                   PCRE2_UTF|PCRE2_UCP|PCRE2_CASELESS, &error, &offset, nullptr),pcre2_code_free);
        if(!code) {
            if(error==PCRE2_ERROR_HEAP_FAILED) throw std::bad_alloc();
            throw std::runtime_error("V2_PREDICATE_COMPILE");
        }
        data.reset(pcre2_match_data_create_from_pattern(code.get(),nullptr));
        if(!data) throw std::bad_alloc();
        for(unsigned i=0;i<128;++i) {
            char c=static_cast<char>(i); ascii[i]=test(&c,1);
        }
    }
    bool test(const char* s, size_t n) {
        int rc=pcre2_match(code.get(),reinterpret_cast<PCRE2_SPTR>(s),n,0,0,data.get(),nullptr);
        if(rc==PCRE2_ERROR_NOMATCH) return false;
        if(rc==PCRE2_ERROR_NOMEMORY) throw std::bad_alloc();
        if(rc<0) throw std::runtime_error("V2_PREDICATE_MATCH");
        return true;
    }
};
struct Node {
    enum Kind { atom, boundary, sequence, alternate, repeat, capture } kind;
    int arg=0, lo=0, hi=0;
    std::vector<Node> children;
    explicit Node(Kind k):kind(k) {}
};
struct Parser {
    const std::string& s; size_t pos=0;
    std::function<int(const std::string&)> predicate;
    Node expression() {
        Node n(Node::alternate); n.children.push_back(sequence());
        while(pos<s.size() && s[pos]=='|') { ++pos; n.children.push_back(sequence()); }
        return n;
    }
    Node sequence() {
        Node n(Node::sequence);
        while(pos<s.size() && s[pos]!=')' && s[pos]!='|') n.children.push_back(piece());
        return n;
    }
    int number() {
        int v=0; size_t begin=pos;
        while(pos<s.size() && s[pos]>='0' && s[pos]<='9') v=v*10+s[pos++]-'0';
        if(begin==pos || v>128) throw std::runtime_error("V2_GRAMMAR_BOUND");
        return v;
    }
    Node piece() {
        Node n(Node::atom);
        if(s[pos]=='(') {
            ++pos;
            if(s.compare(pos,2,"?:")==0) { pos+=2; n=expression(); }
            else if(s.compare(pos,2,"?<")==0) {
                pos+=2; size_t end=s.find('>',pos);
                const std::array<std::string,5> names={"scalar","value","lower","upper","subject"};
                auto it=std::find(names.begin(),names.end(),s.substr(pos,end-pos));
                if(it==names.end()) throw std::runtime_error("V2_GRAMMAR_CAPTURE");
                n=Node(Node::capture); n.arg=static_cast<int>(it-names.begin());
                pos=end+1; n.children.push_back(expression());
            } else throw std::runtime_error("V2_GRAMMAR_GROUP");
            if(pos>=s.size() || s[pos++]!=')') throw std::runtime_error("V2_GRAMMAR_CLOSE");
        } else if(s.compare(pos,2,"\\b")==0) { pos+=2; n=Node(Node::boundary); }
        else {
            size_t begin=pos++;
            if(s[begin]=='[') {
                while(pos<s.size() && s[pos]!=']') ++pos;
                if(pos==s.size()) throw std::runtime_error("V2_GRAMMAR_CLASS");
                ++pos;
            } else if(s[begin]=='\\') ++pos;
            n.arg=predicate(s.substr(begin,pos-begin));
        }
        if(pos<s.size() && (s[pos]=='?' || s[pos]=='+' || s[pos]=='{')) {
            Node r(Node::repeat);
            char q=s[pos++];
            if(q=='?') { r.lo=0; r.hi=1; }
            else if(q=='+') {
                // No other infinite repetition is accepted by this compiler.
                if(n.kind!=Node::atom || n.arg!=predicate("\\s"))
                    throw std::runtime_error("V2_UNBOUNDED_NONSPACE");
                r.lo=1; r.hi=-1;
            } else {
                r.lo=number();
                if(pos>=s.size() || s[pos++]!=',') throw std::runtime_error("V2_GRAMMAR_RANGE");
                r.hi=number();
                if(pos>=s.size() || s[pos++]!='}' || r.hi<r.lo)
                    throw std::runtime_error("V2_GRAMMAR_RANGE");
            }
            r.children.push_back(std::move(n)); return r;
        }
        return n;
    }
};
// Upper bound on consumed non-whitespace scalars. Whitespace is the only
// infinite loop; every new match start consumes a non-whitespace scalar.
size_t nonspace_bound(const Node& n, int space) {
    if(n.kind==Node::atom) return n.arg==space ? 0u : 1u;
    if(n.kind==Node::boundary) return 0;
    size_t total=0;
    for(const auto& c:n.children) {
        size_t b=nonspace_bound(c,space);
        if(n.kind==Node::alternate) total=std::max(total,b);
        else total+=b;
    }
    if(n.kind==Node::repeat) return n.hi<0 ? 0u : total*static_cast<size_t>(n.hi);
    return total;
}
constexpr size_t max_nonspace=512;
constexpr size_t max_instructions=4096;
struct Instruction {
    enum Op { consume, boundary, split, open, close, accept } op;
    int next=0, other=0, arg=0;
};
struct Program {
    std::vector<Instruction> code;
    int entry=0;
    int add(Instruction i) { code.push_back(i); return static_cast<int>(code.size()-1); }
    int compile(const Node& n, int next) {
        switch(n.kind) {
        case Node::atom: return add({Instruction::consume,next,0,n.arg});
        case Node::boundary: return add({Instruction::boundary,next,0,0});
        case Node::capture: {
            int end=add({Instruction::close,next,0,n.arg});
            int begin=compile(n.children[0],end);
            return add({Instruction::open,begin,0,n.arg});
        }
        case Node::sequence:
            for(auto i=n.children.rbegin();i!=n.children.rend();++i) next=compile(*i,next);
            return next;
        case Node::alternate: {
            int tail=compile(n.children.back(),next);
            for(size_t i=n.children.size()-1;i>0;--i) {
                int first=compile(n.children[i-1],next);
                tail=add({Instruction::split,first,tail,0});
            }
            return tail;
        }
        case Node::repeat:
            if(n.hi<0) {
                int loop=add({Instruction::split,0,next,0});
                int body=compile(n.children[0],loop);
                code[loop].next=body;
                return body;
            }
            for(int i=n.lo;i<n.hi;++i) {
                int body=compile(n.children[0],next);
                next=add({Instruction::split,body,next,0});
            }
            for(int i=0;i<n.lo;++i) next=compile(n.children[0],next);
            return next;
        }
        throw std::runtime_error("V2_GRAMMAR_OPCODE");
    }
};
struct Thread {
    int pc=0;
    uint8_t open=0;
    std::array<std::string,5> captures;
};
struct Candidate {
    uint64_t start=0;
    elpis_sha256_ctx hash{};
    std::string text;
    bool omitted=false, done=false, won=false;
    Match winner;
    std::vector<Thread> threads;
    Candidate(int entry,uint64_t at):start(at) {
        elpis_sha256_init(&hash); Thread t; t.pc=entry; threads.push_back(std::move(t));
    }
};
}

struct Lexer::Impl {
    std::map<std::string,int> predicate_ids;
    std::vector<Predicate> predicates;
    std::vector<Program> programs;
    std::vector<std::vector<Candidate>> candidates;
    std::vector<Match> evidence;
    uint32_t limit;
    int word=0;
    uint64_t total=0, position=0;
    elpis_sha256_ctx source{};
    std::array<char,4> decoder{};
    size_t used=0, needed=0;
    bool previous_word=false, active=false;
    Stats measured;
    int predicate(const std::string& s) {
        auto it=predicate_ids.find(s);
        if(it!=predicate_ids.end()) return it->second;
        int id=static_cast<int>(predicates.size());
        predicates.emplace_back(s); predicate_ids.emplace(s,id); return id;
    }
    Impl(const std::vector<std::string>& expressions, uint32_t max, bool use_cache=true):limit(max) {
        elpis_sha256_init(&source);
        if(use_cache) {
            // Fixed grammar compilation is shared and immutable. Match scratch,
            // Unicode predicate results and all stream state remain per handle.
            static const Impl grammar(expressions,0,false);
            predicates.reserve(grammar.predicates.size());
            for(const auto& p:grammar.predicates) predicates.emplace_back(p);
            programs=grammar.programs; word=grammar.word;
            measured.program_instructions=grammar.measured.program_instructions;
            candidates.resize(programs.size());
            return;
        }
        word=predicate("\\w");
        for(const auto& expression:expressions) {
            Parser parser{expression,0,[this](const std::string& s){return predicate(s);}};
            Node tree=parser.expression();
            if(parser.pos!=expression.size()) throw std::runtime_error("V2_GRAMMAR_TRAILING");
            if(nonspace_bound(tree,predicate("\\s"))>max_nonspace)
                throw std::runtime_error("V2_GRAMMAR_NONSPACE_BOUND");
            Program p; int end=p.add({Instruction::accept,0,0,0}); p.entry=p.compile(tree,end);
            if(p.code.size()>max_instructions) throw std::runtime_error("V2_PROGRAM_BOUND");
            measured.program_instructions+=p.code.size(); programs.push_back(std::move(p));
        }
        candidates.resize(programs.size());
    }
    // Ordered Thompson closure: first arrival at a PC wins. Accept cuts only
    // lower-priority paths; greedy higher-priority paths can replace the winner.
    void step(Candidate& c, const Program& p, size_t pi, const char* bytes, size_t n,
              bool boundary, bool eof) {
        if(c.done) return;
        std::vector<Thread> stack, ready;
        std::vector<bool> seen(p.code.size(),false);
        for(auto it=c.threads.rbegin();it!=c.threads.rend();++it) stack.push_back(*it);
        while(!stack.empty()) {
            Thread t=std::move(stack.back()); stack.pop_back();
            if(seen[t.pc]) continue;
            seen[t.pc]=true;
            const auto& i=p.code[t.pc];
            if(i.op==Instruction::consume) { ready.push_back(std::move(t)); continue; }
            if(i.op==Instruction::accept) {
                c.won=true;
                c.winner={pi,c.start,position,c.text,digest(c.hash),c.omitted,t.captures};
                break;
            }
            if(i.op==Instruction::boundary && !boundary) continue;
            if(i.op==Instruction::split) {
                Thread other=t; other.pc=i.other; stack.push_back(std::move(other));
            } else if(i.op==Instruction::open) {
                t.open|=static_cast<uint8_t>(1u<<i.arg); t.captures[i.arg].clear();
            } else if(i.op==Instruction::close) t.open&=static_cast<uint8_t>(~(1u<<i.arg));
            t.pc=i.next; stack.push_back(std::move(t));
        }
        c.threads.clear();
        if(!eof) for(auto& t:ready) {
            const auto& i=p.code[t.pc];
            if(!predicates[i.arg].current) continue;
            for(size_t k=0;k<t.captures.size();++k) if(t.open&(1u<<k)) {
                if(t.captures[k].size()+n>512) throw std::runtime_error("V2_CAPTURE_BOUND");
                t.captures[k].append(bytes,n);
            }
            t.pc=i.next; c.threads.push_back(std::move(t));
        }
        if(c.threads.empty()) { c.done=true; return; }
        elpis_sha256_update(&c.hash,bytes,n);
        if(!c.omitted) {
            if(n>inline_limit-c.text.size()) {
                c.omitted=true; std::string().swap(c.text);
            } else c.text.append(bytes,n);
        }
    }
    void measure() {
        uint64_t nc=0, nt=0, text=0, captures=0;
        for(const auto& rows:candidates) for(const auto& c:rows) {
            ++nc; nt+=c.threads.size(); text+=c.text.capacity()+c.winner.text.capacity();
            for(const auto& t:c.threads) for(const auto& s:t.captures) captures+=s.capacity();
            for(const auto& s:c.winner.captures) captures+=s.capacity();
        }
        measured.peak_candidates=std::max(measured.peak_candidates,nc);
        measured.peak_threads=std::max(measured.peak_threads,nt);
        measured.peak_inline_bytes=std::max(measured.peak_inline_bytes,text);
        measured.peak_capture_bytes=std::max(measured.peak_capture_bytes,captures);
        measured.evidence_count=evidence.size();
    }
    void codepoint(const char* bytes,size_t n,bool eof=false) {
        bool next_word=!eof && (n==1 ? predicates[word].ascii[static_cast<unsigned char>(*bytes)]
                                    : predicates[word].test(bytes,n));
        bool boundary=previous_word!=next_word;
        if(!active && !(boundary && next_word)) {
            previous_word=next_word; position+=n; return;
        }
        for(auto& p:predicates)
            p.current=!eof && (n==1 ? p.ascii[static_cast<unsigned char>(*bytes)] : p.test(bytes,n));
        active=false;
        for(size_t pi=0;pi<programs.size();++pi) {
            auto& rows=candidates[pi]; const auto& p=programs[pi];
            // Every expression begins with a word-boundary + word character.
            // No new starts can accumulate in an infinite whitespace run.
            if(boundary && next_word) {
                if(rows.size()>=max_nonspace+1) throw RangeError{};
                rows.emplace_back(p.entry,position);
            }
            for(auto& c:rows) step(c,p,pi,bytes,n,boundary,eof);
            while(!rows.empty() && rows.front().done) {
                if(!rows.front().won) { rows.erase(rows.begin()); continue; }
                uint64_t end=rows.front().winner.end;
                if(evidence.size()>=limit) throw RangeError{};
                evidence.push_back(std::move(rows.front().winner));
                rows.erase(rows.begin());
                rows.erase(std::remove_if(rows.begin(),rows.end(),[end](const Candidate& c){
                    return c.start<end;
                }),rows.end());
            }
            rows.erase(std::remove_if(rows.begin(),rows.end(),[](const Candidate& c){
                return c.done && !c.won;
            }),rows.end());
        }
        for(const auto& rows:candidates) active=active || !rows.empty();
        previous_word=next_word; position+=n; measure();
    }
    void feed(const uint8_t* data,size_t n) {
        elpis_sha256_update(&source,data,n); total+=n;
        for(size_t i=0;i<n;++i) {
            unsigned c=data[i];
            if(used==0) {
                if(c<128) { char ch=static_cast<char>(c); codepoint(&ch,1); continue; }
                if(c>=0xc2 && c<=0xdf) needed=2;
                else if(c>=0xe0 && c<=0xef) needed=3;
                else if(c>=0xf0 && c<=0xf4) needed=4;
                else throw std::runtime_error("INVALID_UTF8");
            } else {
                if((c&0xc0)!=0x80) throw std::runtime_error("INVALID_UTF8");
                unsigned lead=static_cast<unsigned char>(decoder[0]);
                if(used==1 && ((lead==0xe0 && c<0xa0) || (lead==0xed && c>=0xa0) ||
                   (lead==0xf0 && c<0x90) || (lead==0xf4 && c>=0x90)))
                    throw std::runtime_error("INVALID_UTF8");
            }
            decoder[used++]=static_cast<char>(c);
            if(used==needed) { codepoint(decoder.data(),used); used=0; }
        }
    }
};
Lexer::Lexer(const std::vector<std::string>& e,uint32_t n):impl(new Impl(e,n)) {}
Lexer::~Lexer()=default;
void Lexer::feed(const uint8_t* p,size_t n) { impl->feed(p,n); }
std::vector<Match> Lexer::finish() {
    if(impl->used) throw std::runtime_error("INVALID_UTF8_EOF");
    impl->codepoint(nullptr,0,true);
    return std::move(impl->evidence);
}
Stats Lexer::stats() const { return impl->measured; }
uint64_t Lexer::bytes() const { return impl->total; }
std::string Lexer::source_digest() const { return digest(impl->source); }
}
