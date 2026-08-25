from __future__ import annotations
import argparse, tempfile
from pathlib import Path
from safetensors.torch import load_file, save_file
from elpis_reference.model import MODEL_REPO,MODEL_REVISION,MODEL_SHA256,UPSTREAM_TRM_COMMIT,REGISTERED_PARAMETER_COUNT,CONVERTED_STATE_SHA256,verify_model,load_model

def metadata(): return {"source_repo":MODEL_REPO,"source_revision":MODEL_REVISION,"source_sha256":MODEL_SHA256,"upstream_trm_commit":UPSTREAM_TRM_COMMIT,"registered_parameter_count":str(REGISTERED_PARAMETER_COUNT)}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--model",type=Path,required=True); args=ap.parse_args()
    verified=verify_model(args.model)
    if verified["converted_state_sha256"]!=CONVERTED_STATE_SHA256: raise RuntimeError("trusted model digest did not match constant")
    state=load_file(str(args.model),device="cpu")
    key=next(k for k in sorted(state) if state[k].numel()>0 and state[k].dtype.is_floating_point)
    mutated={k:v.clone() for k,v in state.items()}; flat=mutated[key].reshape(-1)
    flat[0]=flat[0]+1
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); bad=td/"tampered.safetensors"; save_file(mutated,str(bad),metadata=metadata())
        try: verify_model(bad)
        except RuntimeError as exc:
            if "converted model state SHA-256 mismatch" not in str(exc): raise
        else: raise RuntimeError("tampered tensor state passed verify_model")
        try: load_model(model_path=bad,device="cpu")
        except RuntimeError: pass
        else: raise RuntimeError("tampered tensor state passed load_model")
        badmeta=td/"badmeta.safetensors"; m=metadata(); m["source_sha256"]="0"*64; save_file(state,str(badmeta),metadata=m)
        try: verify_model(badmeta)
        except RuntimeError as exc:
            if "metadata mismatch" not in str(exc): raise
        else: raise RuntimeError("tampered metadata passed verify_model")
    print("MODEL_INTEGRITY_REDTEAM=PASS"); return 0
if __name__=="__main__": raise SystemExit(main())
