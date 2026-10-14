"""Compact JSON Schemas for model consumers.

Pydantic's schemas are written for people reading API docs: titles on every
field, class docstrings (with their ``Attributes:`` sections) as
descriptions, and ``$ref`` indirection for every named type. A model reading
them over a voice call pays for all of that in latency and context, and
learns nothing new from it. `compact` strips the noise and inlines small
definitions, keeping every constraint.
"""

__all__: tuple[str, ...] = ("compact",)

from typing import Any, Final

_DROP: Final = frozenset({"title"})


def compact(schema: dict[str, Any]) -> dict[str, Any]:
    """A smaller schema with the same constraints.

    - Inlines every ``$ref`` (input schemas here aren't recursive), without
      the referenced type's docstring.
    - Drops ``title``s, which only restate the property name.
    - Trims descriptions to their first paragraph, dropping docstring
      sections like ``Attributes:`` that duplicate per-field information.

    Example:
        >>> compact(
        ...     {
        ...         "$defs": {"C": {"title": "C", "enum": ["a", "b"]}},
        ...         "properties": {"x": {"$ref": "#/$defs/C", "title": "X"}},
        ...         "title": "In",
        ...         "description": "Input.",
        ...     }
        ... )
        {'properties': {'x': {'enum': ['a', 'b']}}, 'description': 'Input.'}
    """
    definitions: dict[str, Any] = schema.get("$defs", {})

    def walk(node: Any) -> Any:  # noqa: ANN401 - any JSON
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            target = definitions[node["$ref"].rsplit("/", 1)[-1]]
            # A shared type's docstring describes the type, not this field:
            # the field's own description (if any) says what it's for.
            target = {k: v for k, v in target.items() if k != "description"}
            merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
            return walk(merged)
        result: dict[str, Any] = {}
        for key, value in node.items():
            if key in _DROP or key == "$defs":
                continue
            if key == "description" and isinstance(value, str):
                result[key] = value.split("\n\n", 1)[0].strip()
            elif key == "properties" and isinstance(value, dict):
                result[key] = {name: walk(prop) for name, prop in value.items()}
            else:
                result[key] = walk(value)
        return result

    compacted: dict[str, Any] = walk(schema)
    return compacted
