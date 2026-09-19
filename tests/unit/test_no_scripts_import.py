from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"


def _imports_scripts(module_path: Path) -> bool:
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "scripts" or alias.name.startswith("scripts."):
                    return True
        if isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "scripts" or node.module.startswith("scripts.")):
                return True
    return False


def test_app_modules_do_not_import_scripts() -> None:
    offenders: list[str] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        if _imports_scripts(path):
            offenders.append(str(path.relative_to(APP_ROOT.parent)))
    assert offenders == []
