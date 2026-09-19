from __future__ import annotations

import re
from pathlib import Path

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
PLACEHOLDER_PATTERN = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


class SqlTemplateError(Exception):
    """Invalid SQL template configuration."""


def quote_identifier(identifier: str) -> str:
    if not IDENTIFIER_PATTERN.match(identifier):
        raise SqlTemplateError(f"Invalid SQL identifier: {identifier}")
    return f'"{identifier}"'


def validate_identifier(identifier: str) -> str:
    if not IDENTIFIER_PATTERN.match(identifier):
        raise SqlTemplateError(f"Invalid SQL identifier: {identifier}")
    return identifier


def load_sql_template(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def render_sql_template(
    template: str,
    identifiers: dict[str, str] | None = None,
    fragments: dict[str, str] | None = None,
) -> str:
    rendered = template
    for key, value in (fragments or {}).items():
        rendered = rendered.replace("{{" + key + "}}", value)
    for key, value in (identifiers or {}).items():
        placeholder = "{{" + key + "}}"
        if placeholder not in rendered:
            continue
        rendered = rendered.replace(placeholder, quote_identifier(value))
    remaining = PLACEHOLDER_PATTERN.findall(rendered)
    if remaining:
        raise SqlTemplateError(f"Unresolved SQL placeholders: {remaining}")
    return rendered


def expand_in_list(sql: str, params: dict[str, object]) -> tuple[str, dict[str, object]]:
    expanded_sql = sql
    expanded_params: dict[str, object] = {}
    for key, value in params.items():
        placeholder = f":in_{key}"
        if placeholder in expanded_sql:
            if not isinstance(value, list):
                raise SqlTemplateError(f"Expected list for :in_{key}")
            if not value:
                raise SqlTemplateError(f"Empty IN list for :in_{key}")
            bind_names = []
            for index, item in enumerate(value):
                bind_name = f"{key}_{index}"
                bind_names.append(f"%({bind_name})s")
                expanded_params[bind_name] = item
            expanded_sql = expanded_sql.replace(placeholder, "(" + ", ".join(bind_names) + ")")
        else:
            expanded_params[key] = value
    return expanded_sql, expanded_params
