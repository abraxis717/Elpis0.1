#ifndef ELPIS_STREAMING_REGEX_BOUNDED_FILE_STAGING_H
#define ELPIS_STREAMING_REGEX_BOUNDED_FILE_STAGING_H

#include <cstddef>
#include <istream>
#include <string>
#include <utility>
#include <vector>

namespace elpis_streaming_regex_detail {

enum class BoundedFileStageStatus {
    Ok,
    InputExceedsCarry,
    InputRead
};

struct BoundedFileStageResult {
    BoundedFileStageStatus status;
    std::string data;
};

/*
 * Stage a complete stream before any lexical processing.
 *
 * Successful admission requires genuine EOF. A read failure is never
 * interpreted as EOF, even if some prefix bytes were already obtained.
 */
inline BoundedFileStageResult stage_bounded_stream(
    std::istream &f,
    std::size_t chunk_size,
    std::size_t carry_bytes)
{
    std::vector<char> buf(chunk_size);
    std::string data;

    for(;;) {
        f.read(
            buf.data(),
            static_cast<std::streamsize>(buf.size()));

        const std::streamsize got=f.gcount();

        if(got<0) {
            return {
                BoundedFileStageStatus::InputRead,
                std::move(data)
            };
        }

        if(got>0) {
            const std::size_t n=
                static_cast<std::size_t>(got);

            /*
             * The invariant data.size() <= carry_bytes is established at
             * initialization and preserved by the guarded append.
             */
            if(n > carry_bytes-data.size()) {
                return {
                    BoundedFileStageStatus::InputExceedsCarry,
                    std::move(data)
                };
            }

            data.append(buf.data(),n);
        }

        /*
         * badbit wins over eofbit: an I/O error is not successful EOF.
         */
        if(f.bad()) {
            return {
                BoundedFileStageStatus::InputRead,
                std::move(data)
            };
        }

        /*
         * eofbit establishes that the staged bytes are the complete stream.
         * A normal short final read and the zero-byte read following an
         * exact-multiple final chunk both arrive here with failbit also set.
         */
        if(f.eof()) {
            return {
                BoundedFileStageStatus::Ok,
                std::move(data)
            };
        }

        /*
         * Any remaining fail state is a non-EOF read failure.
         */
        if(f.fail()) {
            return {
                BoundedFileStageStatus::InputRead,
                std::move(data)
            };
        }

        /*
         * A zero-byte read with a nominally good stream cannot prove EOF and
         * must not spin or delegate a partial task.
         */
        if(got==0) {
            return {
                BoundedFileStageStatus::InputRead,
                std::move(data)
            };
        }
    }
}

} // namespace elpis_streaming_regex_detail

#endif
