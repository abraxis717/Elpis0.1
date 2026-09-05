# Elpis2.1.0

Elpis2.1.0 ships `BASIC_REGEX_SHIPMENT_R1`.

## StreamingRegexIngress v1

The supported lexical-input profile is now explicit:

- `carry_bytes >= 256`
- complete `data_len <= carry_bytes`

Chunk segmentation is transport-level only inside that admitted profile.
Inputs outside the profile fail with `ELPIS_STREAMING_REGEX_E_RANGE`,
`INPUT_EXCEEDS_CARRY`, and no result publication.

The standalone CLI additionally requires genuine EOF before lexical
delegation. Non-EOF read failure returns `INPUT_READ` and emits no JSON.

The exact 1174-byte contradictory Phase-1 counterexample is rejected by the
default 1024-byte profile and is correctly retained when a caller supplies
carry >= 1174.

## Compatibility and authority

- Public C ABI remains v1.
- Accepted-domain R0 -> R1 behavior was byte-exact in the qualified
  differential.
- Historical R0 fixture evidence is not invalidated.
- The generalized R0 arbitrary-streaming claim is superseded.
- Arbitrary-length streaming is not claimed.
- Regex remains model-free and authority-zero.
- No semantic, admission, execution, persistent-graph, P4, Grid81, embedding,
  or new runtime authority is granted by this release.
