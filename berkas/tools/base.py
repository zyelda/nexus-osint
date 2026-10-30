from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolEntity:
    type: str
    value: str
    normalized: str
    confidence: float = 0.6
    attributes: dict = field(default_factory=dict)
    key: str = ""


@dataclass
class ToolEdge:
    source_key: str
    target_key: str
    relation: str
    confidence: float = 0.6
    attributes: dict = field(default_factory=dict)


@dataclass
class ToolEvidence:
    category: str
    weight: float = 1.0
    source_url: str = ""
    snippet: str = ""
    entity_key: str = ""
    edge_key: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class ToolResult:
    status: str = "success"
    data: dict = field(default_factory=dict)
    entities: list[ToolEntity] = field(default_factory=list)
    edges: list[ToolEdge] = field(default_factory=list)
    evidence: list[ToolEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error_code: str = ""
    error_message: str = ""

    @property
    def ok(self) -> bool:
        return self.status in {"success", "partial", "not_found"}


@dataclass
class ToolSpec:
    id: str
    label: str
    description: str
    inputs: list[str]
    outputs: list[str]
    run: Callable[[str, dict], ToolResult]
    requires_key: str = ""
    timeout_s: int = 18
    legal_note: str = ""
    category: str = "general"


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.id in self._tools:
            raise ValueError(f"Tool sudah terdaftar: {spec.id}")
        self._tools[spec.id] = spec

    def get(self, tool_id: str) -> ToolSpec | None:
        return self._tools.get(tool_id)

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def for_type(self, entity_type: str) -> list[ToolSpec]:
        return [tool for tool in self._tools.values() if entity_type in tool.inputs]

    def public(self, settings) -> list[dict]:
        return [
            {
                "id": tool.id,
                "label": tool.label,
                "description": tool.description,
                "inputs": tool.inputs,
                "outputs": tool.outputs,
                "category": tool.category,
                "requires_key": tool.requires_key,
                "configured": bool(getattr(settings, tool.requires_key.lower(), "")) if tool.requires_key else True,
                "legal_note": tool.legal_note,
            }
            for tool in self._tools.values()
        ]


def ok(data: dict, entities=None, edges=None, evidence=None, warnings=None) -> ToolResult:
    return ToolResult(
        status="success",
        data=data,
        entities=entities or [],
        edges=edges or [],
        evidence=evidence or [],
        warnings=warnings or [],
    )


def partial(data: dict, warnings=None, entities=None, edges=None, evidence=None) -> ToolResult:
    return ToolResult(
        status="partial",
        data=data,
        entities=entities or [],
        edges=edges or [],
        evidence=evidence or [],
        warnings=warnings or [],
    )


def not_found(data: dict, warnings=None) -> ToolResult:
    return ToolResult(status="not_found", data=data, warnings=warnings or [])


def fail(code: str, message: str, warnings=None) -> ToolResult:
    return ToolResult(status="error", error_code=code, error_message=message, warnings=warnings or [])


def missing_key(key: str) -> ToolResult:
    return ToolResult(
        status="missing_key",
        error_code="missing_key",
        error_message=f"{key} belum dikonfigurasi.",
    )


def entity(type_: str, value: str, normalized: str, confidence: float = 0.6, **attributes) -> ToolEntity:
    return ToolEntity(
        type=type_,
        value=value,
        normalized=normalized,
        confidence=confidence,
        attributes=attributes,
        key=f"{type_}:{normalized}",
    )


def edge(source_key: str, target_key: str, relation: str, confidence: float = 0.6, **attributes) -> ToolEdge:
    return ToolEdge(
        source_key=source_key,
        target_key=target_key,
        relation=relation,
        confidence=confidence,
        attributes=attributes,
    )


def evidence(
    category: str,
    weight: float,
    source_url: str = "",
    snippet: str = "",
    entity_key: str = "",
    edge_key: str = "",
    **raw: Any,
) -> ToolEvidence:
    return ToolEvidence(
        category=category,
        weight=weight,
        source_url=source_url,
        snippet=snippet[:800],
        entity_key=entity_key,
        edge_key=edge_key,
        raw=raw,
    )
