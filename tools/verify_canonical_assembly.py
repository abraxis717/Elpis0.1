import json
import pathlib
import sys

CANONICAL_ONLY = {"elpis_nanbeige42_host"}
NON_SHIPPED_PATHS = (
    "components/elpis_nanbeige42_host",
    "native/elpis-nanbeige42-host",
)

def load_json(file_path, label, errors):
    if not file_path.exists():
        errors.append(f"Missing {label}: {file_path}")
        return None
    try:
        return json.loads(file_path.read_text())
    except Exception as exc:
        errors.append(f"Invalid {label}: {exc}")
        return None

def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    errors = []
    canonical = load_json(root / "ELPIS_CANONICAL_MANIFEST.json", "canonical manifest", errors)
    public = load_json(root / "manifests/PUBLIC_COMPONENT_REGISTRY.json", "public component registry", errors)
    graph = load_json(root / "manifests/PUBLIC_DEPENDENCY_GRAPH.json", "public dependency graph", errors)
    if canonical is None or public is None or graph is None:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"FAIL: {len(errors)} error(s)")
        return 1

    if canonical.get("component_count") != 17:
        errors.append(f"Canonical component_count must be 17, got {canonical.get('component_count')}")
    if public.get("component_count") != 16:
        errors.append(f"Public component_count must be 16, got {public.get('component_count')}")
    if canonical.get("runtime_admission") is not False:
        errors.append("Canonical runtime_admission must be false")
    if public.get("runtime_admission") is not False:
        errors.append("Public runtime_admission must be false")

    canonical_components = canonical.get("components", [])
    public_components = public.get("components", [])
    canonical_ids = [item.get("component_id") for item in canonical_components]
    public_ids = [item.get("component_id") for item in public_components]
    if len(canonical_ids) != len(set(canonical_ids)):
        errors.append("Duplicate component_id in canonical manifest")
    if len(public_ids) != len(set(public_ids)):
        errors.append("Duplicate component_id in public registry")

    expected_public = set(canonical_ids) - CANONICAL_ONLY
    if set(public_ids) != expected_public:
        errors.append(
            "Public registry must equal canonical inventory minus canonical-only components: "
            f"missing={sorted(expected_public - set(public_ids))} "
            f"extra={sorted(set(public_ids) - expected_public)}"
        )
    if not CANONICAL_ONLY <= set(canonical_ids):
        errors.append("Canonical-only component declaration absent from canonical inventory")

    graph_nodes = graph.get("nodes", [])
    if len(graph_nodes) != len(set(graph_nodes)) or set(graph_nodes) != expected_public:
        errors.append("Public dependency graph nodes must equal public component IDs")
    for edge in graph.get("edges", []):
        if edge.get("from") not in expected_public or edge.get("to") not in expected_public:
            errors.append(f"Public dependency edge references non-public component: {edge}")

    public_by_id = {item.get("component_id"): item for item in public_components if item.get("component_id")}
    for component_id in sorted(expected_public):
        public_component = public_by_id.get(component_id)
        if public_component is None:
            continue
        if public_component.get("runtime_admission") is not False:
            errors.append(f"{component_id}: public registry runtime_admission must be false")
        relative = public_component.get("public_path")
        if not isinstance(relative, str) or not relative:
            errors.append(f"{component_id}: invalid public_path")
            continue
        relative_path = pathlib.Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            errors.append(f"{component_id}: unsafe public_path {relative}")
            continue
        component_root = root / relative_path
        manifest_path = component_root / "COMPONENT_MANIFEST.json"
        if not component_root.is_dir():
            errors.append(f"{component_id}: missing public component path {relative}")
            continue
        if not manifest_path.is_file():
            errors.append(f"{component_id}: missing COMPONENT_MANIFEST.json at {relative}")
            continue
        try:
            component_manifest = json.loads(manifest_path.read_text())
        except Exception as exc:
            errors.append(f"{component_id}: invalid component manifest: {exc}")
            continue
        if component_manifest.get("component_id") != component_id:
            errors.append(f"{component_id}: manifest component_id mismatch {component_manifest.get('component_id')}")
        if component_manifest.get("runtime_admission") is not False:
            errors.append(f"{component_id}: component runtime_admission must be false")

    for relative in NON_SHIPPED_PATHS:
        if (root / relative).exists():
            errors.append(f"Canonical-only Nanbeige host path shipped: {relative}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"FAIL: {len(errors)} error(s)")
        return 1
    print("PASS: Public assembly verified through 16 shipped mappings plus 1 canonical-only component")
    return 0

if __name__ == "__main__":
    sys.exit(main())
