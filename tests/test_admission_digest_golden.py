"""Exact Elpis2.1.9 receipt identities recorded before admission edits."""
from elpis_reference.structural_guidance.receipt import StructuralGuidanceReceiptV1, SCHEMA


def test_historical_bypassed_receipt():
    receipt = StructuralGuidanceReceiptV1(
        schema=SCHEMA, outcome='BYPASSED', enabled=False,
        projection_digest='429542da40728160105b2d449deb4fac0d929ec697b2d35d6a3eb9dc06b4292a',
        envelope_digest='',
        input_refinement_fingerprint='e87415150311aa5f27ba0549095c2c3b1d16b231245485e8df37f3d3d3dd2a49',
        output_refinement_fingerprint='', checkpoint_sha256='',
        seed=0, budget=128, restarts=8, plateau=25,
        iterations=0, best_cost=-1, applied_moves=0, authority_granted=0,
    )
    assert receipt.receipt_digest == 'b372e15762733708209c1f8f4e945bad0e4858d2ad0fc7aa06824ac7d2d0cff5'


def test_historical_admitted_receipt():
    receipt = StructuralGuidanceReceiptV1(
        schema=SCHEMA, outcome='ADMITTED', enabled=True,
        projection_digest='1'*64, envelope_digest='2'*64,
        input_refinement_fingerprint='3'*64, output_refinement_fingerprint='4'*64,
        checkpoint_sha256='5'*64, seed=0, budget=128, restarts=8, plateau=25,
        iterations=2, best_cost=0, applied_moves=1, authority_granted=0,
    )
    assert receipt.receipt_digest == '48e96be01a70d9de152524857fd38e8604712e3af34c63d492519cef78bb9e39'


def test_successor_inactive_receipts():
    from elpis_reference.structural_guidance.inactive_receipt import InactiveGuidanceReceiptV2, UnavailableDetail
    bypassed = InactiveGuidanceReceiptV2('BYPASSED', '1'*64, '2'*64, ())
    unavailable = InactiveGuidanceReceiptV2('FALLBACK_REQUIRED', '1'*64, '2'*64, (
        UnavailableDetail('TORCH_UNAVAILABLE', 'AdmissionUnavailable', 'Optional torch runtime is unavailable.'),
    ))
    assert bypassed.receipt_digest == '522d0ec30e8d4115845ebfa50ab0887e2b88f38eb3dfe00871e316475c3254cb'
    assert unavailable.receipt_digest == 'e9bacf9bed90169f939005c1be671b7f0bb3b414489504690c18f89b88a6efe7'
    assert bypassed.validate_digest() and unavailable.validate_digest()
    object.__setattr__(unavailable, 'projection_digest', '3'*64)
    assert not unavailable.validate_digest()
