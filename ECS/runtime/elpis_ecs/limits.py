"""Immutable protocol limits, bound into genesis authority."""
MAX_INT = (1 << 63) - 1
MAX_FRAME_BYTES = 262144
MAX_PAYLOAD_BYTES = 65536
MAX_STRING_BYTES = 1024
PROTOCOL = {
    "revision": "ecs.m1a.integration.v3",
    "max_int": MAX_INT,
    "max_frame_bytes": MAX_FRAME_BYTES,
    "max_payload_bytes": MAX_PAYLOAD_BYTES,
    "max_string_bytes": MAX_STRING_BYTES,
    "scheduler": "active-mailbox-fifo/entity-id-before-founded-activation.v1",
    "lifecycle": "founded-active-dormant-terminal.v1",
}
