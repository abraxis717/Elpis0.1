import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
BLOCK_TORCH = '''
import importlib.abc, sys
class NoTorch(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'torch' or fullname.startswith('torch.'):
            raise ModuleNotFoundError('torch intentionally absent', name='torch')
sys.meta_path.insert(0, NoTorch())
'''


def test_packaging_extra():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
    for path in ('pyproject.toml', 'runtime/R0/pyproject.toml', 'components/TRMFractalSpine/pyproject.toml'):
        dependencies = tomllib.loads((ROOT / path).read_text())['project']['dependencies']
        assert not any(d.startswith('torch') for d in dependencies), path
    assert 'torch>=2.2' in project['optional-dependencies']['trm']


def test_deterministic_imports_and_execution_without_torch():
    code = BLOCK_TORCH + '''
import numpy as np
import elpis.contracts
from elpis.contracts import state_equal
from elpis.contracts.codecs.grid_numpy_torch import bytes_from_np, np_from_bytes, torch_from_np
import elpis_reference.cli
import elpis_reference.refinement
import elpis_reference.structural_guidance
from elpis_reference.structural_guidance._authority.c2r6p0.projector import project
from elpis_reference.structural_guidance._authority.c2r6p0.contracts import ProjectionInputV1
from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import SemanticOperationV1, build_semantic_request_v1
request = build_semantic_request_v1(request_id='base', entities=(), operations=(SemanticOperationV1('A', 'step'),))
assert project(ProjectionInputV1.from_signed(request)).error is None
from elpis_reference.structural_guidance._authority.core import run_guided_search
from elpis_reference.sudoku import parse_puzzle, validate
assert state_equal(np.zeros(81), np.zeros(81))
assert len(np_from_bytes(bytes_from_np(np.zeros(81, dtype=np.uint8)))[0]) == 81
assert len(parse_puzzle('.' * 81)) == 81
assert 'torch' not in sys.modules
from elpis_reference.model import fetch_model, load_model
from elpis_reference.refinement import solve_sudoku
for operation in (
    lambda: torch_from_np(np.zeros(81, dtype=np.uint8)),
    fetch_model,
    load_model,
    lambda: solve_sudoku((0,) * 81),
):
    try:
        operation()
    except ModuleNotFoundError as exc:
        assert 'elpis[trm]' in str(exc)
    else:
        raise AssertionError('TRM call should require extra')
print('torch_modules=0')
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'torch_modules=0'


def test_torch_codec_when_installed():
    import pytest
    torch = pytest.importorskip('torch')
    import numpy as np
    from elpis.contracts.codecs.grid_numpy_torch import torch_from_np, np_from_torch
    grid = np.arange(81, dtype=np.uint8) % 10
    tensor = torch_from_np(grid)
    assert tensor.dtype == torch.long
    assert np.array_equal(np_from_torch(tensor)[0], grid)


def test_unrelated_import_failure_is_not_masked(monkeypatch):
    from elpis import optional_dependencies
    error = ModuleNotFoundError('broken torch dependency', name='unrelated_dependency')
    def broken(_name):
        raise error
    monkeypatch.setattr(optional_dependencies, 'import_module', broken)
    import pytest
    with pytest.raises(ModuleNotFoundError) as caught:
        optional_dependencies.require_torch()
    assert caught.value is error


def test_model_architecture_with_extra():
    import pytest
    torch = pytest.importorskip('torch')
    from elpis_reference.model import _new_model, REGISTERED_PARAMETER_COUNT
    model = _new_model(torch.device('cpu'))
    assert sum(p.numel() for p in model.parameters()) == REGISTERED_PARAMETER_COUNT


def test_r0_transaction_without_torch():
    paths = [ROOT / 'src', ROOT / 'components', ROOT / 'runtime/R0/src']
    paths += [ROOT / 'components' / p / 'src' for p in (
        'Pipeline/P0ControlProtocol', 'TRMFractalSpine',
        'Grid81DeterministicStructuralAdjudicator', 'Grid81StructuralSemantics',
    )]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, paths)))
    code = BLOCK_TORCH + '''
from elpis_runtime_r0.transaction import execute_r0_transaction
first = execute_r0_transaction()
second = execute_r0_transaction()
assert first.receipt_bytes() == second.receipt_bytes()
assert 'torch' not in sys.modules
'''
    subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env, check=True)
