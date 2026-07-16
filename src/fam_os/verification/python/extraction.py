"""Extract the first syntactically valid Python candidate."""

import ast
import re


_PYTHON_FENCE = re.compile(
    r"```(?:python|py)?\s*\n(.*?)```", flags=re.DOTALL | re.IGNORECASE
)


def extract_python_candidate(content: str) -> str:
    candidates = _PYTHON_FENCE.findall(content) or [content]
    errors: list[str] = []
    for candidate in candidates:
        code = candidate.strip()
        if not code:
            continue
        try:
            ast.parse(code)
        except SyntaxError as error:
            errors.append(str(error))
            continue
        return code
    detail = "; ".join(errors[:2]) or "no Python source found"
    raise ValueError(detail)
