from __future__ import annotations
import hashlib,json
from elpis_p0.canonical import digest
from elpis_p0.contracts import ArtifactCandidate,RequestContext
from elpis_p0.factory import build_default_controller
from elpis_p0.lineage_authority import P0LineageAuthorityError,P0LineageAuthorityReceiptV1,RECEIPT_DOMAIN

class RejectingDecoder:
    def decode(self,context,plan):
        source="def solution(:\n    return 1\n"
        return ArtifactCandidate(language="python",source=source,digest=digest({"plan_digest":plan.plan_digest,"source":source}))

def dd(domain,payload):
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
    return hashlib.sha256(domain.encode()+b"\\x00"+raw).hexdigest()

def main():
    ctx=RequestContext(request_id="c2r6ca-e2e",prompt="write deterministic python and validate it",domain="python",entrypoint="solution",parameters=("x",))
    c=build_default_controller(); c.decoder=RejectingDecoder(); r=c.run(ctx)
    if r.accepted: raise RuntimeError("fixture accepted")
    a=c.authorized_artifact_lineage(r,validator_index=0); v=c.lineage_authority_verifier()
    consumption=v.consume(receipt=a.receipt,lineage=a.lineage)
    replay=False
    try: v.consume(receipt=a.receipt,lineage=a.lineage)
    except P0LineageAuthorityError: replay=True
    if not replay: raise RuntimeError("replay accepted")
    other=build_default_controller(); cross=False
    try: other.lineage_authority_verifier().consume(receipt=a.receipt,lineage=a.lineage)
    except P0LineageAuthorityError: cross=True
    if not cross: raise RuntimeError("cross-controller accepted")
    base={"authority_instance_id":v.authority_instance_id,"capability_id":"c"*64,"issuance_sequence":777,"lineage_digest":a.lineage.lineage_digest,"p0_result_digest":a.lineage.p0_result_digest,"request_id":a.lineage.request_id,"validator_evidence_digest":a.lineage.validator_evidence_digest,"validator_index":a.lineage.validator_index}
    fake=P0LineageAuthorityReceiptV1(**base,receipt_digest=dd(RECEIPT_DOMAIN,base)); forged=False
    try: v.consume(receipt=fake,lineage=a.lineage)
    except P0LineageAuthorityError: forged=True
    if not forged: raise RuntimeError("unissued self-consistent receipt accepted")
    print(json.dumps({"schema":"elpis.public-c2r6ca-controller-authority-primitive.v1","status":"PASS","claims":{"controller_precommit_before_result_return":True,"one_shot_registry_consumption":True,"replay_rejected":replay,"cross_controller_rejected":cross,"self_consistent_unissued_receipt_rejected":forged,"production_validator_ingress_requires_receipt":False,"external_attestation":False,"cross_process_durability":False,"runtime_admission":False}},sort_keys=True))
    return 0
if __name__=="__main__": raise SystemExit(main())
