"""Test authority boundary and forbidden field checks."""

import sys
import os

BASE = '/mnt/primesauce/Elpis_Canon'
PACKAGE = os.path.join(BASE, 'Grid81StructuralGroupProjectionCompiler')
sys.path.insert(0, os.path.join(PACKAGE, 'src'))


def test_no_activation_imports():
    """G5.0B package must not import activation modules."""
    pkg_dir = os.path.join(PACKAGE, 'src', 'elpis_grid81_groups')
    forbidden_imports = [
        'elpis_grid81_groups.adjudication',
        'elpis_grid81_groups.activation',
        'elpis_grid81_groups.router',
        'elpis_grid81_groups.runtime',
    ]
    for forbidden in forbidden_imports:
        mod_path = os.path.join(pkg_dir, forbidden.replace('.', os.sep))
        assert not os.path.exists(mod_path), f"Forbidden module exists: {forbidden}"


def test_no_forbidden_package_paths():
    """G5.0B must not have forbidden subdirectories."""
    pkg_dir = os.path.join(PACKAGE, 'src', 'elpis_grid81_groups')
    forbidden = ['adjudication', 'activation', 'router', 'runtime']
    for name in os.listdir(pkg_dir):
        full = os.path.join(pkg_dir, name)
        if os.path.isdir(full) and name not in forbidden:
            pass
        elif os.path.isdir(full) and name in forbidden:
            assert False, f"Forbidden directory: {name}"


def test_forbidden_terms_in_source():
    """Source files must not contain forbidden import patterns."""
    pkg_dir = os.path.join(PACKAGE, 'src', 'elpis_grid81_groups')
    forbidden_patterns = [
        'import torch',
        'from torch',
        'import transformers',
        'CUDA',
        'llama.cpp',
        'model loaders',
        'adapter loaders',
        'ECS runtime',
        'subprocess-based execution',
        'capability issuer',
        'capability consumer',
    ]
    for fname in os.listdir(pkg_dir):
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(pkg_dir, fname)
        with open(fpath, 'r') as f:
            content = f.read()
        for pattern in forbidden_patterns:
            assert pattern not in content, f"Forbidden pattern '{pattern}' in {fname}"


def test_authority_boundary_report():
    """Authority boundary report should indicate no activation authority."""
    reports = os.path.join(BASE, 'reports', 'G5_0B_StructuralGroupProjectionCompiler')
    path = os.path.join(reports, 'G50B_AUTHORITY_BOUNDARY_AUDIT.json')
    if os.path.exists(path):
        import json
        with open(path, 'r') as f:
            data = json.load(f)
        assert data['status'] == 'ACTIVATION_AUTHORITY_UNREPRESENTABLE'

