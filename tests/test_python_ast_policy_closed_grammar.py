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


@pytest.mark.parametrize('source', [
    '@help\ndef solution():\n    pass',
    '@memoryview\ndef solution():\n    pass',
    '@help\nasync def solution():\n    pass',
    '@help\nclass K:\n    pass\ndef solution():\n    pass',
    'class K(metaclass=type):\n    pass\ndef solution():\n    pass',
    'class K(int):\n    pass\ndef solution():\n    pass',
    'class K:\n    pass\ndef solution():\n    pass',
    'def solution(x):\n    with x as y:\n        pass',
    'async def solution(x):\n    async with x as y:\n        pass',
    't = type\ndef solution():\n    pass',
    'def solution():\n    return len',
    'def solution():\n    return [help, memoryview]',
    'def solution():\n    raise BaseException',
    'def solution():\n    raise SystemExit',
    'def solution():\n    raise KeyboardInterrupt',
    'def solution():\n    raise GeneratorExit',
    'def solution(error):\n    raise error',
    'def solution():\n    raise OSError()',
])
def test_implicit_capability_forms_rejected(source):
    decision = evaluate_python_ast_policy(language='python', source=source, entrypoint='solution')
    assert decision.code == 'BANNED_CALL' and not decision.passed
    evidence = PythonASTValidator().validate(
        RequestContext(request_id='implicit', prompt='', entrypoint='solution'),
        ArtifactCandidate(language='python', source=source, digest=''),
    )
    assert not evidence.passed and evidence.code == 'BANNED_CALL'


@pytest.mark.parametrize('exception', ['ValueError', 'TypeError', 'IndexError', 'KeyError', 'RuntimeError', 'Exception'])
def test_explicitly_admitted_raised_exceptions(exception):
    for expression in (exception, f'{exception}("invalid input")'):
        assert evaluate_python_ast_policy(language='python', entrypoint='solution',
            source=f'def solution():\n    raise {expression}').passed

def test_typed_handler_admitted_and_bare_handler_rejected_without_new_code():
    typed = (
        "def solution(x):\n"
        "    try:\n"
        "        return int(x)\n"
        "    except ValueError:\n"
        "        return 0\n"
    )
    bare = (
        "def solution(x):\n"
        "    try:\n"
        "        return int(x)\n"
        "    except:\n"
        "        return 0\n"
    )

    typed_decision = evaluate_python_ast_policy(
        language="python",
        source=typed,
        entrypoint="solution",
    )
    bare_decision = evaluate_python_ast_policy(
        language="python",
        source=bare,
        entrypoint="solution",
    )

    assert typed_decision.passed
    assert typed_decision.code == "AST_VALID"
    assert not bare_decision.passed
    assert bare_decision.code == "BANNED_CALL"
    assert bare_decision.call_name == "<bare-except>"


def test_non_admitted_typed_handler_remains_banned_call():
    source = (
        "def solution(x):\n"
        "    try:\n"
        "        return int(x)\n"
        "    except BaseException:\n"
        "        return 0\n"
    )
    decision = evaluate_python_ast_policy(
        language="python",
        source=source,
        entrypoint="solution",
    )
    assert not decision.passed
    assert decision.code == "BANNED_CALL"
    assert decision.call_name == "BaseException"


def test_nested_definition_does_not_satisfy_module_entrypoint():
    source = (
        "def outer():\n"
        "    def solution(x):\n"
        "        return x\n"
        "    return 1\n"
    )
    decision = evaluate_python_ast_policy(
        language="python",
        source=source,
        entrypoint="solution",
    )
    assert not decision.passed
    assert decision.code == "ENTRYPOINT_MISSING"
    assert "solution" in decision.functions
