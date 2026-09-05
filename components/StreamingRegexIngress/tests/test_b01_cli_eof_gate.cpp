#include "bounded_file_staging.h"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <streambuf>
#include <string>

using elpis_streaming_regex_detail::BoundedFileStageResult;
using elpis_streaming_regex_detail::BoundedFileStageStatus;
using elpis_streaming_regex_detail::stage_bounded_stream;

static void req(bool ok,const char *msg) {
    if(!ok) {
        std::cerr << "FAIL " << msg << "\n";
        std::exit(1);
    }
}

class ThrowingReadBuf final : public std::streambuf {
public:
    ThrowingReadBuf(
        std::string first_chunk,
        bool fail_first)
        : first_chunk_(std::move(first_chunk)),
          fail_first_(fail_first)
    {}

protected:
    std::streamsize xsgetn(
        char *dst,
        std::streamsize count) override
    {
        ++calls_;

        if(fail_first_ || calls_>1)
            throw std::ios_base::failure(
                "B01_TEST_INJECTED_READ_FAILURE");

        req(
            count>=0,
            "negative stream read count");

        req(
            static_cast<std::size_t>(count) <=
                first_chunk_.size(),
            "fault fixture first chunk too short");

        std::memcpy(
            dst,
            first_chunk_.data(),
            static_cast<std::size_t>(count));

        return count;
    }

private:
    std::string first_chunk_;
    bool fail_first_=false;
    unsigned calls_=0;
};

static void require_ok(
    const std::string &input,
    std::size_t chunk,
    std::size_t carry,
    const char *msg)
{
    std::istringstream in(input);

    const BoundedFileStageResult r=
        stage_bounded_stream(
            in,
            chunk,
            carry);

    req(r.status==BoundedFileStageStatus::Ok,msg);
    req(r.data==input,"successful staging changed bytes");
}

int main() {
    /*
     * Empty file: first zero-byte read establishes EOF.
     */
    require_ok(
        "",
        64,
        256,
        "empty file did not establish EOF");

    /*
     * Short final read: bytes are retained and EOF admits them.
     */
    require_ok(
        "touching endpoints may merge; maximum end.",
        64,
        256,
        "short final read failed");

    /*
     * Exact-multiple file: two exact reads remain good, then the following
     * zero-byte read establishes EOF.
     */
    require_ok(
        std::string(128,'x'),
        64,
        256,
        "exact-multiple EOF failed");

    /*
     * Oversized stream: reject before append even though the same read also
     * discovers EOF.
     */
    {
        std::istringstream in(std::string(257,'x'));

        const BoundedFileStageResult r=
            stage_bounded_stream(
                in,
                4096,
                256);

        req(
            r.status==
                BoundedFileStageStatus::InputExceedsCarry,
            "oversized stream was not range rejected");
    }

    /*
     * First-read I/O failure: no EOF was established.
     */
    {
        ThrowingReadBuf buf("",true);
        std::istream in(&buf);

        const BoundedFileStageResult r=
            stage_bounded_stream(
                in,
                64,
                1024);

        req(
            r.status==BoundedFileStageStatus::InputRead,
            "first-read failure was treated as EOF");

        req(
            r.data.empty(),
            "first-read failure staged unexpected bytes");
    }

    /*
     * After-prefix I/O failure.
     *
     * The first transport chunk is a valid lexical prefix. The next read
     * faults at exactly the point where an unread contradictory or oversized
     * suffix could have followed. The prefix may remain staged internally,
     * but the disposition must be InputRead, never successful admission.
     */
    {
        std::string prefix=
            "touching endpoints may merge; maximum end.";

        req(
            prefix.size() <= 64u,
            "prefix fixture unexpectedly exceeds one chunk");

        prefix.append(64u-prefix.size(),' ');

        ThrowingReadBuf buf(prefix,false);
        std::istream in(&buf);

        const BoundedFileStageResult r=
            stage_bounded_stream(
                in,
                64,
                1024);

        req(
            r.status==BoundedFileStageStatus::InputRead,
            "after-prefix failure was treated as EOF");

        req(
            r.data==prefix,
            "after-prefix fault did not preserve exact staged prefix");
    }

    /*
     * Non-EOF failbit is also rejection, not completion.
     */
    {
        std::istringstream in("ignored");
        in.setstate(std::ios::failbit);

        const BoundedFileStageResult r=
            stage_bounded_stream(
                in,
                64,
                256);

        req(
            r.status==BoundedFileStageStatus::InputRead,
            "non-EOF failbit was treated as EOF");
    }

    std::cout
        << "PASS_STREAMING_REGEX_B01_CLI_EOF_GATE_R2\n";

    return 0;
}
