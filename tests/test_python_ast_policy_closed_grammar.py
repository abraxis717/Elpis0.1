"""Static rejection is not an execution sandbox or a correctness claim."""
import pytest
from elpis.python_ast_policy import evaluate_python_ast_policy
from elpis_p0.validators import PythonASTValidator
from elpis_p0.contracts import ArtifactCandidate, RequestContext


@pytest.mark.parametrize('expression', [
    "(x for x in ()).gi_frame.f_builtins['eval']('__import__(\"os\").system(\"echo pwned\")')",
    "obj.cr_frame.f_globals['eval']('1')",
    "obj.ag_frame.f_builtins['exec']('pass')",
    "obj.tb_frame.f_locals['f']()",
    "obj.gi_code.co_consts[0]",
    "obj.cr_code.co_names", "obj.ag_code.co_consts", "obj.f_back",
    "obj.tb_next", "obj.co_code", "obj.gi_yieldfrom", "obj.cr_await", "obj.ag_await",
    "callbacks['ev' + 'al']('1')", "factory()('1')",
    "obj.unknown", "obj.append",  # no method recovery/aliasing
])
def test_recovery_and_indirect_calls_rejected(expression):
    decision = evaluate_python_ast_policy(language='python', source=f'def solution(obj=None):\n    return {expression}\n', entrypoint='solution')
    assert not decision.passed
    assert decision.code == 'BANNED_CALL'


@pytest.mark.parametrize('bans', [frozenset(), frozenset({'print'})])
@pytest.mark.parametrize('name', ['eval', 'exec', 'compile', 'open', '__import__', 'breakpoint'])
def test_core_bans_cannot_be_subtracted(bans, name):
    source = f'def solution():\n    return {name}("1")\n'
    assert not evaluate_python_ast_policy(language='python', source=source, entrypoint='solution', banned_calls=bans).passed
    validator = PythonASTValidator()
    validator.banned_calls = bans
    assert not validator.validate(RequestContext(request_id='test', prompt='', entrypoint='solution'), ArtifactCandidate(language='python', source=source, digest='')).passed


@pytest.mark.parametrize('source', [
    'def solution(xs):\n    out = []\n    for x in sorted(xs):\n        out.append(x)\n    return out\n',
    'def solution(xs):\n    return [x[0] for x in xs if len(x)]\n',
    'def solution(xs):\n    xs.sort(key=lambda x: x[0])\n    return xs\n',
    'def solution(d):\n    return [(k, v) for k, v in d.items()]\n',
    'def solution(s):\n    return s.strip().lower().split()\n',
    'def helper(x):\n    return x + 1\ndef solution(x):\n    return helper(x)\n',
])
def test_ordinary_generated_python(source):
    assert evaluate_python_ast_policy(language='python', source=source, entrypoint='solution').passed
