#!/usr/bin/env python3
import json,pathlib
def main():
    root=pathlib.Path(__file__).parent.parent
    m=json.loads((root/"ELPIS_CANONICAL_MANIFEST.json").read_text())
    r=json.loads((root/"COMPONENT_REGISTRY.json").read_text())
    print(f"Assembly: {m.get('assembly_version')}  Components: {m.get('component_count')}")
    for c in r.get("components",[]):
        deps=", ".join(c.get("dependencies",[])) or "none"
        print(f"  {c['promotion_order']}. {c['component_id']} ({c.get('active_path_status')}) deps=[{deps}]")
if __name__=="__main__": main()
