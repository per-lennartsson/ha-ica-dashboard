"""The domain package must stay free of Home Assistant imports."""

import ast
from pathlib import Path

DOMAIN_DIR = Path(__file__).parent.parent / "custom_components" / "handla" / "domain"


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def test_domain_modules_do_not_import_home_assistant() -> None:
    files = sorted(DOMAIN_DIR.glob("*.py"))
    assert files, "domain package not found"
    for path in files:
        offenders = {
            m for m in _imported_modules(path) if m.split(".")[0] == "homeassistant"
        }
        assert not offenders, f"{path.name} imports {offenders}"
