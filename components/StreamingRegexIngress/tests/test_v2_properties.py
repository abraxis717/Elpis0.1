"""Deterministic ABI differential properties; no installed Python packages needed.

Usage: python3 test_v2_properties.py /path/to/native/library.so
The long-match oracle deliberately transforms only the documented V2 evidence
representation. It does not weaken lexical, offset, payload or digest equality.
"""
import ctypes as C
import hashlib
import json
import random
import sys


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class ABI:
    def __init__(self, path):
        self.lib = C.CDLL(path)
        signatures = {
            "parse_bytes_v1": ([C.c_char_p, C.c_size_t, C.c_size_t, C.c_size_t, C.POINTER(C.c_void_p)], C.c_int),
            "stream_create_v2": ([C.c_void_p, C.POINTER(C.c_void_p)], C.c_int),
            "stream_feed_v2": ([C.c_void_p, C.c_char_p, C.c_size_t], C.c_int),
            "stream_finalize_v2": ([C.c_void_p, C.POINTER(C.c_void_p)], C.c_int),
            "stream_destroy_v2": ([C.c_void_p], None),
            "result_json_v1": ([C.c_void_p], C.c_char_p),
            "result_destroy_v1": ([C.c_void_p], None),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.lib, "elpis_streaming_regex_" + name)
            fn.argtypes, fn.restype = args, result
            setattr(self, name, fn)

    def v1(self, source):
        result = C.c_void_p()
        rc = self.parse_bytes_v1(source, len(source), len(source) + 1, max(256, len(source)), C.byref(result))
        try:
            return rc, self.result_json_v1(result) if result else None
        finally:
            self.result_destroy_v1(result)

    def v2(self, source, chunks):
        stream, result = C.c_void_p(), C.c_void_p()
        assert self.stream_create_v2(None, C.byref(stream)) == 0
        offset, rc = 0, 0
        try:
            for size in chunks:
                data = source[offset:offset + size]
                rc = self.stream_feed_v2(stream, data, len(data))
                offset += len(data)
                if rc:
                    break
            if not rc and offset < len(source):
                rc = self.stream_feed_v2(stream, source[offset:], len(source) - offset)
            if not rc:
                rc = self.stream_finalize_v2(stream, C.byref(result))
            assert not rc or not result.value
            return rc, self.result_json_v1(result) if result else None
        finally:
            self.result_destroy_v1(result)
            self.stream_destroy_v2(stream)


def long_representation(raw):
    value = json.loads(raw)
    omitted = False
    for evidence in value["ingress"]["evidence"]:
        if len(evidence["matched_text"].encode()) > 4096:
            omitted = True
            del evidence["matched_text"]
            del evidence["evidence_id"]
            evidence["matched_text_omitted"] = True
            evidence["schema"] = "elpis.regex-lexical-evidence.v2"
            evidence["evidence_id"] = hashlib.sha256(canonical(evidence)).hexdigest()
    if omitted:
        value["ingress"]["schema"] = "elpis.regex-stream-ingress-result.v2"
    return canonical(value)


def main(path):
    abi = ABI(path)
    rng = random.Random(0xE1F152)
    phrases = [
        "at least +1.25", "strictly greater than -2.5", "at most .5", "strictly less than 2",
        "not equal to 7", "exactly equal to 4", "keep value between low and high",
        "low is the lower bound", "high as upper limit", "touching endpoints do not merge",
        "strictly overlapping", "touching ranges may also merge", "maximum ending coordinate", "minimum right edge",
    ]
    runs = 0
    # Exact representational transition, including source offsets and match hash.
    for length in [4095, 4096, 4097, 16384]:
        source = b"at" + b" " * (length - 9) + b"least 1"
        rc, oracle = abi.v1(source)
        assert rc == 0
        for chunk in [1, 2, 17, len(source)]:
            got = abi.v2(source, [chunk] * (len(source) // chunk + 1))
            assert got == (0, long_representation(oracle)), ("inline transition", length, chunk)
            runs += 1
    # Every family spans far more than V1's default carry; arbitrary whitespace
    # is hashed in original order, not collapsed or normalized.
    for phrase in phrases:
        source = phrase.replace(" ", " \t\r\n" * 1300).encode()
        rc, oracle = abi.v1(source)
        assert rc == 0
        expected = long_representation(oracle)
        for chunk in [17, 4093, len(source)]:
            assert abi.v2(source, [chunk] * (len(source) // chunk + 1)) == (0, expected), phrase
            runs += 1
    # Sparse input has full V1 identity despite exceeding historical carry.
    source = b"; ".join(p.encode() for p in phrases)
    sparse = b"z" * (2 * 1024 * 1024) + b"; " + source
    expected = abi.v1(sparse)
    assert expected[0] == 0
    assert abi.v2(sparse, [65521] * 34) == expected
    runs += 1
    # Deterministic mutation/property corpus: overlapping alternatives, Unicode
    # word/space/caseless behavior, bounded captures, malformed input and EOF.
    alphabet = [";", " ", "\t", "\u00a0", "\u2003", "\u0301", "\u212a", "\u017f", "π", "😀", "0", ".", "+", "-", "_", "X", "\0"]
    for i in range(300):
        text = rng.choice(phrases) + rng.choice(alphabet) + rng.choice(phrases)
        for _ in range(rng.randrange(1, 5)):
            pos = rng.randrange(len(text) + 1)
            text = text[:pos] + rng.choice(alphabet) + text[pos + rng.randrange(2):]
        source = text.encode()
        if i % 7 == 0:
            pos = rng.randrange(len(source) + 1)
            source = source[:pos] + bytes([rng.randrange(128, 256)]) + source[pos:]
        expected = abi.v1(source)
        sizes = [rng.randrange(1, 24) for _ in range(len(source))]
        for chunks in [[1] * len(source), sizes, [len(source)]]:
            got = abi.v2(source, chunks)
            assert (got[0] == 0) == (expected[0] == 0), (i, source)
            if not got[0]:
                assert got == expected, (i, source)
                result = json.loads(got[1])
                assert result["ingress"]["source_sha256"] == hashlib.sha256(source).hexdigest()
                assert result["ingress"]["source_bytes"] == len(source)
            runs += 1
    # Pathological near-prefix and number streams cannot grow pending source.
    for source in [b"at lea " * 4096, b"touching endpoints do not " * 1024,
                   b"at least " + b"9" * 65536, b"touching endpoints " + b"x " * 8192]:
        assert abi.v2(source, [8191] * (len(source) // 8191 + 1)) == abi.v1(source)
        runs += 1
    print(f"PASS_V2_PROPERTIES runs={runs}; 14 long families; inline transition; sparse parity; seeded mutation")


if __name__ == "__main__":
    main(sys.argv[1])
