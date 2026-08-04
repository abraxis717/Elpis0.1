"""Stable error taxonomy for P14 host callers."""

class ElpisHostError(Exception):
    """Base class for all host ABI failures."""

class ManifestMismatch(ElpisHostError): pass
class DigestRuleViolation(ElpisHostError): pass
class HookResolutionFailure(ElpisHostError): pass
class HookInvocationDrift(ElpisHostError): pass
class GenerationShapeViolation(ElpisHostError): pass
class ControlShapeMismatch(ElpisHostError): pass
class PacketDerivationUnavailable(ElpisHostError): pass
class PacketDerivationViolation(ElpisHostError): pass
class PacketDerivationInputMismatch(PacketDerivationViolation): pass
class PacketDerivationMethodUnsupported(PacketDerivationViolation): pass
class ExplicitControlVectorInvalid(PacketDerivationViolation): pass
class RegistryDerivationUnavailable(PacketDerivationViolation): pass
class Grid81DerivationForbidden(PacketDerivationViolation): pass
class UnsupportedControlMode(ElpisHostError): pass
class ActuationCapabilityViolation(ElpisHostError): pass
class ActuationCapabilityConsumed(ActuationCapabilityViolation): pass
class ActuationCapabilityExpired(ActuationCapabilityViolation): pass
class ActuationCapabilityScopeMismatch(ActuationCapabilityViolation): pass
class ActionSchemaViolation(ElpisHostError): pass
class ExecutorPolicyViolation(ElpisHostError): pass
class WorkspacePreimageMismatch(ElpisHostError): pass
class PatchTransactionViolation(ElpisHostError): pass
class VerificationFailure(ElpisHostError): pass
class EvidenceDigestFailure(ElpisHostError): pass
class CacheFingerprintMissing(ElpisHostError): pass
class DeterministicReplayFailure(ElpisHostError): pass
class RuntimeQualificationRequired(ElpisHostError): pass
class RuntimeProfileInvalid(ElpisHostError): pass
class RuntimeModeUnqualified(ElpisHostError): pass
class ModelIdentityDrift(ElpisHostError): pass
class CacheEquivalenceFailure(ElpisHostError): pass
class SeamULPQualificationFailure(ElpisHostError): pass
class HookTeardownFailure(ElpisHostError): pass
class RuntimeReplayFailure(ElpisHostError): pass
