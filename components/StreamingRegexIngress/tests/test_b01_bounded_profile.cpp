#include "streaming_regex_ingress.h"

#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

static void req(bool ok, const char *msg) {
    if (!ok) {
        std::cerr << "FAIL " << msg << "\n";
        std::exit(1);
    }
}

static std::string parse_ok(
    const std::string &input,
    size_t chunk,
    size_t carry,
    bool require_fail_closed)
{
    elpis_streaming_regex_result_v1 *r = nullptr;

    const int rc = elpis_streaming_regex_parse_bytes_v1(
        reinterpret_cast<const uint8_t *>(input.data()),
        input.size(),
        chunk,
        carry,
        &r);

    if (rc != ELPIS_STREAMING_REGEX_OK) {
        std::cerr
            << "FAIL parse_ok rc=" << rc
            << " chunk=" << chunk
            << " carry=" << carry
            << " len=" << input.size()
            << " error=" << elpis_streaming_regex_last_error_v1()
            << "\n";
        std::exit(1);
    }

    req(r != nullptr, "successful parse returned null result");
    req(
        elpis_streaming_regex_result_source_bytes_v1(r) == input.size(),
        "successful parse reported wrong source byte count");

    if (require_fail_closed) {
        req(
            elpis_streaming_regex_result_fail_closed_v1(r) == 1,
            "contradictory accepted task did not fail closed");
        req(
            elpis_streaming_regex_result_ambiguity_count_v1(r) >= 1,
            "contradictory accepted task did not retain ambiguity");
    }

    const char *json = elpis_streaming_regex_result_json_v1(r);
    req(json != nullptr, "result JSON is null");

    std::string out(json);
    elpis_streaming_regex_result_destroy_v1(r);
    return out;
}

static void parse_range(
    const std::string &input,
    size_t chunk,
    size_t carry)
{
    /*
     * Deliberately poison the caller slot. The ABI must clear it before any
     * parsing and range rejection must never publish a partial result.
     */
    elpis_streaming_regex_result_v1 *r =
        reinterpret_cast<elpis_streaming_regex_result_v1 *>(0x1);

    const int rc = elpis_streaming_regex_parse_bytes_v1(
        reinterpret_cast<const uint8_t *>(input.data()),
        input.size(),
        chunk,
        carry,
        &r);

    if (rc != ELPIS_STREAMING_REGEX_E_RANGE) {
        std::cerr
            << "FAIL expected E_RANGE rc=" << rc
            << " chunk=" << chunk
            << " carry=" << carry
            << " len=" << input.size()
            << " error=" << elpis_streaming_regex_last_error_v1()
            << "\n";
        std::exit(1);
    }

    req(r == nullptr, "range failure published a Regex result");

    const char *err = elpis_streaming_regex_last_error_v1();
    req(err != nullptr, "range failure has null error");
    req(
        std::strcmp(err, "INPUT_EXCEEDS_CARRY") == 0,
        "unexpected range error text");
}

static std::string pad_to(
    const std::string &prefix,
    size_t target)
{
    req(prefix.size() <= target, "pad target smaller than fixture");
    std::string out = prefix;
    out.append(target - out.size(), ' ');
    return out;
}

static void require_chunk_invariant(
    const std::string &input,
    size_t carry,
    const std::vector<size_t> &chunks,
    const char *msg)
{
    std::string baseline;

    for (size_t chunk : chunks) {
        const std::string got =
            parse_ok(input, chunk, carry, true);

        if (baseline.empty())
            baseline = got;
        else
            req(got == baseline, msg);
    }
}


/* B01_UTF8_SUCCESSOR_R1 */
static void require_parse_error(
    const std::string &input,
    size_t chunk,
    size_t carry,
    const char *expected_error)
{
    elpis_streaming_regex_result_v1 *r =
        reinterpret_cast<elpis_streaming_regex_result_v1 *>(0x1);

    const int rc = elpis_streaming_regex_parse_bytes_v1(
        reinterpret_cast<const uint8_t *>(input.data()),
        input.size(),
        chunk,
        carry,
        &r);

    if (rc != ELPIS_STREAMING_REGEX_E_PARSE) {
        std::cerr
            << "FAIL expected E_PARSE rc=" << rc
            << " chunk=" << chunk
            << " carry=" << carry
            << " len=" << input.size()
            << " error=" << elpis_streaming_regex_last_error_v1()
            << "\n";
        std::exit(1);
    }

    req(r == nullptr, "UTF-8 parse failure published a result");

    const char *err = elpis_streaming_regex_last_error_v1();
    req(err != nullptr, "UTF-8 parse failure has null error");
    req(
        std::strcmp(err, expected_error) == 0,
        "unexpected UTF-8 parse error");
}

int main() {
    const std::vector<size_t> chunks = {1, 2, 3, 7, 13, 64, 4096};

    req(
        ELPIS_STREAMING_REGEX_MIN_CARRY_BYTES_V1 == 256u,
        "unexpected v1 minimum carry");
    req(
        ELPIS_STREAMING_REGEX_DEFAULT_CARRY_BYTES_V1 == 1024u,
        "unexpected v1 default carry");

    const std::string contradictory =
        "touching endpoints do not merge; "
        "touching endpoints may merge; maximum end.";

    /*
     * Existing compact contradiction remains byte-identical across transport
     * segmentation when admitted by the caller's carry profile.
     */
    require_chunk_invariant(
        contradictory,
        1024,
        chunks,
        "compact contradiction is chunk-sensitive");

    /*
     * Explicit carry-1 / carry / carry+1 matrices at both the minimum carry
     * and the historical default carry.
     *
     * The accepted fixtures retain contradictory evidence. The +1 fixture
     * must fail before lexical result publication.
     */
    for (size_t carry : {
            static_cast<size_t>(ELPIS_STREAMING_REGEX_MIN_CARRY_BYTES_V1),
            static_cast<size_t>(ELPIS_STREAMING_REGEX_DEFAULT_CARRY_BYTES_V1)}) {

        const std::string below =
            pad_to(contradictory, carry - 1);
        const std::string exact =
            pad_to(contradictory, carry);
        const std::string over =
            pad_to(contradictory, carry + 1);

        require_chunk_invariant(
            below,
            carry,
            chunks,
            "carry-1 accepted input is chunk-sensitive");

        require_chunk_invariant(
            exact,
            carry,
            chunks,
            "carry-exact accepted input is chunk-sensitive");

        for (size_t chunk : chunks)
            parse_range(over, chunk, carry);
    }

    /*
     * Exact Astra B01 counterexample.
     *
     * R0:
     *   small chunks could retire the early negative relation before final
     *   disposition while a whole-buffer chunk retained it.
     *
     * R1 containment:
     *   - carry 1024: reject, because 1174 > 1024;
     *   - carry 1174: accept with the complete task retained through EOF;
     *   - carry 4096: accept for the same reason.
     *
     * All accepted transport segmentations must produce byte-identical
     * canonical JSON and preserve contradiction/fail-closed behavior.
     */
    const std::string astra =
        std::string("touching endpoints do not merge.") +
        std::string(1100, ' ') +
        "touching endpoints may merge; maximum end.";

    req(astra.size() == 1174, "Astra fixture length changed");

    for (size_t chunk : chunks)
        parse_range(astra, chunk, 1024);

    std::string astra_baseline;

    for (size_t carry : {astra.size(), static_cast<size_t>(4096)}) {
        for (size_t chunk : chunks) {
            const std::string got =
                parse_ok(astra, chunk, carry, true);

            if (astra_baseline.empty())
                astra_baseline = got;
            else
                req(
                    got == astra_baseline,
                    "accepted Astra counterexample is chunk/carry-sensitive");
        }
    }

    /*
     * A caller may choose a carry larger than the historical 1024-byte
     * default. The default is not an absolute input-size ceiling.
     */
    const std::string above_default =
        pad_to(contradictory, 1536);

    require_chunk_invariant(
        above_default,
        1536,
        chunks,
        "input above default carry ceiling was not correctly admitted");

    /*
     * Accepted UTF-8 boundary split.
     *
     * With chunk=1 and other small chunk sizes the leading pi and trailing
     * snowman are split across transport boundaries. The contradictory lexical
     * task is still admitted wholly inside carry and must remain byte-identical.
     */
    const std::string utf8_accepted =
        std::string("\xcf\x80 ") +
        contradictory +
        std::string(" \xe2\x98\x83");

    require_chunk_invariant(
        utf8_accepted,
        1024,
        chunks,
        "accepted UTF-8 boundary split is chunk-sensitive");

    /*
     * Malformed and incomplete UTF-8 must continue to fail with no result.
     */
    std::string malformed =
        "touching endpoints may merge; maximum end. ";
    malformed.push_back(static_cast<char>(0xc3));
    malformed.push_back('(');

    std::string incomplete =
        "touching endpoints may merge; maximum end. ";
    incomplete.push_back(static_cast<char>(0xe2));
    incomplete.push_back(static_cast<char>(0x82));

    for (size_t chunk : chunks) {
        require_parse_error(
            malformed,
            chunk,
            1024,
            "INVALID_UTF8");

        require_parse_error(
            incomplete,
            chunk,
            1024,
            "INVALID_UTF8_EOF");
    }

    std::cout
        << "PASS_STREAMING_REGEX_B01_BOUNDED_PROFILE_R1\n";

    return 0;
}
