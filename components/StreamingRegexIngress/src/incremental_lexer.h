#ifndef ELPIS_INCREMENTAL_LEXER_H
#define ELPIS_INCREMENTAL_LEXER_H
#include "elpis/sha256.h"
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace elpis_regex_v2 {
constexpr size_t inline_limit = 4096;
struct Match {
    size_t pattern = 0;
    uint64_t start = 0, end = 0;
    std::string text, digest;
    bool text_omitted = false;
    // scalar, value, lower, upper, subject; byte-exact, never normalized.
    std::array<std::string, 5> captures;
};
struct RangeError {};
struct Stats {
    uint64_t peak_candidates = 0, peak_threads = 0;
    uint64_t peak_inline_bytes = 0, peak_capture_bytes = 0;
    uint64_t program_instructions = 0, evidence_count = 0;
};
class Lexer {
public:
    Lexer(const std::vector<std::string>& expressions, uint32_t max_evidence);
    ~Lexer();
    Lexer(const Lexer&) = delete;
    Lexer& operator=(const Lexer&) = delete;
    void feed(const uint8_t*, size_t);
    std::vector<Match> finish();
    Stats stats() const;
    uint64_t bytes() const;
    std::string source_digest() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};
}
#endif
