from __future__ import annotations

from copy import deepcopy
from typing import Any

UNSUPPORTED_SCHEMA_KEYWORDS = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "maxItems",
    "uniqueItems",
}


def sanitize_schema_for_strict(schema: dict[str, Any]) -> dict[str, Any]:
    root = deepcopy(schema)
    defs = root.pop("$defs", None) or root.pop("definitions", None) or {}

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                key = ref.split("/")[-1]
                if key not in defs:
                    raise ValueError(f"Unknown schema reference: {ref}")
                return resolve(deepcopy(defs[key]))
            if "allOf" in node and len(node["allOf"]) == 1:
                merged = resolve(node["allOf"][0])
                if isinstance(merged, dict):
                    for key, value in node.items():
                        if key != "allOf":
                            merged[key] = value
                    return resolve(merged)
            cleaned: dict[str, Any] = {}
            description_parts: list[str] = []
            existing_description = node.get("description")
            if isinstance(existing_description, str) and existing_description.strip():
                description_parts.append(existing_description.strip())
            for key, value in node.items():
                if key in UNSUPPORTED_SCHEMA_KEYWORDS:
                    description_parts.append(f"{key}: {value}")
                    continue
                if key == "minItems" and isinstance(value, int) and value > 1:
                    description_parts.append(f"minItems: {value}")
                    continue
                if key == "allOf":
                    continue
                cleaned[key] = resolve(value)
            if cleaned.get("type") == "object":
                cleaned["additionalProperties"] = False
            if description_parts:
                cleaned["description"] = " ".join(description_parts)
            return cleaned
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(root)
