import json
import pathlib
import sys

def load_json(file_path, label, errors):
    if not file_path.exists():
        errors.append(f"Missing {label}: {file_path.relative_to(file_path.parent.parent) if file_path.parent.parent in file_path.parents else file_path}")
        return None
    try:
        return json.loads(file_path.read_text())
    except Exception as exc:
        errors.append(f"Invalid {label}: {exc}")
        return None

def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    errors = []

    canonical_path = root / "ELPIS_CANONICAL_MANIFEST.json"
    public_path = root / "manifests" / "PUBLIC_COMPONENT_REGISTRY.json"

    canonical = load_json(canonical_path, "canonical manifest", errors)
    public = load_json(public_path, "public component registry", errors)

    if canonical is None or public is None:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"FAIL: {len(errors)} error(s)")
        return 1

    if canonical.get("component_count") != 17:
        errors.append(f"Canonical component_count must be 17, got {canonical.get('component_count')}")

    if public.get("component_count") != 17:
        errors.append(f"Public component_count must be 17, got {public.get('component_count')}")

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

    missing_public = sorted(set(canonical_ids) - set(public_ids))
    extra_public = sorted(set(public_ids) - set(canonical_ids))

    for component_id in missing_public:
        errors.append(f"Canonical component missing from public registry: {component_id}")

    for component_id in extra_public:
        errors.append(f"Public registry component absent from canonical manifest: {component_id}")

    public_by_id = {
        item.get("component_id"): item
        for item in public_components
        if item.get("component_id")
    }

    for canonical_component in canonical_components:
        component_id = canonical_component.get("component_id")
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
            errors.append(
                f"{component_id}: manifest component_id mismatch "
                f"{component_manifest.get('component_id')}"
            )

        if component_manifest.get("runtime_admission") is not False:
            errors.append(f"{component_id}: component runtime_admission must be false")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"FAIL: {len(errors)} error(s)")
        return 1

    print("PASS: Public assembly verified through 17 canonical-to-public component mappings")
    return 0

if __name__ == "__main__":
    sys.exit(main())
