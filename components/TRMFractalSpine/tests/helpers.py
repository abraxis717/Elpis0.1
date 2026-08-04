"""Test helpers — used by codec tests."""

from elpis_fractal_spine.codec_contracts import (
    CodecAdmissionStatus,
    CodecClass,
    EvidenceCodecManifest,
    NativeEvidenceKind,
)


def create_manifest(
    codec_id: str,
    implementation_digest: str = "impl_v1",
    source_model_id: str = "__synthetic_fixture__",
    admission_status: CodecAdmissionStatus = CodecAdmissionStatus.TEST_ONLY,
) -> EvidenceCodecManifest:
    """Create a minimal valid manifest for testing."""
    return EvidenceCodecManifest(
        codec_id=codec_id,
        codec_version="0.1.0",
        codec_class=CodecClass.DETERMINISTIC_NUMERIC,
        source_model_id=source_model_id,
        source_semantic_space="fixture.native.vector81.v1",
        source_abi_version="elpis.fixture.vector81.v1",
        source_shape=(81,),
        source_dtype="float64",
        target_evidence_kind=NativeEvidenceKind.CELL_ALIGNED_EVIDENCE,
        target_semantic_space="latent.trm-orthogonal.cell81.v1",
        target_abi_version="elpis.trm-orthogonal-latent.v1",
        target_shape=(81,),
        target_dtype="float64",
        implementation_digest=implementation_digest,
        evaluation_corpus_digest="eval_corpus_v1",
        deterministic_mode="pass_through",
        admission_status=admission_status,
        authority_class="PURE_EVIDENCE_TRANSFORM",
        context_fields=("request_id", "node_id", "target_space_digest", "target_basis_digest"),
    )
