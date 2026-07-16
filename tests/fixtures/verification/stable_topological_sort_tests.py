import ast
import copy
import inspect


def _assert_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _candidate_source():
    try:
        return __FAM_CANDIDATE_SOURCE__
    except NameError:
        return inspect.getsource(stable_topological_sort)


def _assert_candidate_contract():
    tree = ast.parse(_candidate_source())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    _assert_equal([node.name for node in functions], ["stable_topological_sort"], "one function")
    function = functions[0]
    if function.end_lineno - function.lineno + 1 > 50:
        raise AssertionError("stable_topological_sort must be at most 50 lines")
    forbidden_calls = {
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in {"set", "min", "sorted"}
    }
    if forbidden_calls or any(isinstance(node, (ast.Set, ast.SetComp)) for node in ast.walk(function)):
        raise AssertionError("set, min, and sorted are forbidden")


def _assert_unchanged(graph, expected, label):
    before = copy.deepcopy(graph)
    actual = stable_topological_sort(graph)
    _assert_equal(actual, expected, label)
    _assert_equal(graph, before, f"{label} input mutation")


_assert_candidate_contract()


_assert_unchanged(
    {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []},
    ["A", "B", "C", "D"],
    "stable branch order",
)

_assert_unchanged(
    {"root": ["neighbor_only"]},
    ["root", "neighbor_only"],
    "neighbor-only node",
)

_assert_unchanged(
    {"B": ["D"], "A": ["D"], "D": []},
    ["B", "A", "D"],
    "input order for simultaneous roots",
)

_assert_unchanged(
    {"A": [], "B": [], "C": []},
    ["A", "B", "C"],
    "disconnected stable order",
)

try:
    stable_topological_sort({"A": ["B"], "B": ["A"]})
except ValueError:
    pass
else:
    raise AssertionError("cycle must raise ValueError")
