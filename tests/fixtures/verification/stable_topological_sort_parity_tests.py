def _assert_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


_assert_equal(
    stable_topological_sort({"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}),
    ["A", "B", "C", "D"],
    "stable branch order",
)

_assert_equal(
    stable_topological_sort({"root": ["neighbor_only"]}),
    ["root", "neighbor_only"],
    "neighbor-only node",
)

_assert_equal(
    stable_topological_sort({"B": ["D"], "A": ["D"], "D": []}),
    ["B", "A", "D"],
    "input order for simultaneous roots",
)

_assert_equal(
    stable_topological_sort({"A": [], "B": [], "C": []}),
    ["A", "B", "C"],
    "disconnected stable order",
)

try:
    stable_topological_sort({"A": ["B"], "B": ["A"]})
except ValueError:
    pass
else:
    raise AssertionError("cycle must raise ValueError")
