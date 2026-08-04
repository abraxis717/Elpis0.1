#!/usr/bin/env python3
import json,hashlib,sys,pathlib
def sha256f(f):
    h=hashlib.sha256()
    with open(f,"rb") as fh:
        for c in iter(lambda:fh.read(65536),b""): h.update(c)
    return h.hexdigest()
def main():
    root=pathlib.Path(__file__).parent.parent;errors=[]
    mp=root/"ELPIS_CANONICAL_MANIFEST.json"
    if not mp.exists(): sys.exit(1)
    m=json.loads(mp.read_text())
    if m.get("runtime_admission"): errors.append("runtime_admission")
    if m.get("component_count")!=17: errors.append("Expected 17")
    for c in m.get("components",[]):
        cm=root/c["relative_path"]/"COMPONENT_MANIFEST.json"
        if not cm.exists(): errors.append(f"Missing: {c['relative_path']}")
        else:
            c2=json.loads(cm.read_text())
            if c2.get("runtime_admission"): errors.append(f"{c['component_id']}: runtime")
    if errors: print(f"FAIL: {len(errors)}"); sys.exit(1)
    print("PASS: Assembly verified (17 components)"); sys.exit(0)
if __name__=="__main__": main()
