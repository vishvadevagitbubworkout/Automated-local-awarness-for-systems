from __future__ import annotations

from app.capabilities.templates import (
    APPROVED_CAPABILITY_TEMPLATES,
    CapabilityTemplateDefinition,
)


class CapabilityRegistryError(ValueError):
    """Controlled registry error for missing, duplicate, or ambiguous capabilities."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


class CapabilityRegistry:
    """Deterministic registry for developer-defined capability templates."""

    def __init__(
        self,
        templates: list[CapabilityTemplateDefinition] | None = None,
    ):
        self._templates: dict[str, CapabilityTemplateDefinition] = {}
        source_templates = list(templates) if templates is not None else list(APPROVED_CAPABILITY_TEMPLATES)
        for template in source_templates:
            self.register(template)

    def register(self, template: CapabilityTemplateDefinition) -> CapabilityTemplateDefinition:
        if not isinstance(template, CapabilityTemplateDefinition):
            raise TypeError("CapabilityRegistry.register expects a CapabilityTemplateDefinition.")

        capability_id = template.capability_id
        normalized_capability = capability_id.lower()
        if "llm" in normalized_capability or "capability" in normalized_capability:
            raise CapabilityRegistryError(
                "CAPABILITY_NOT_FOUND",
                "Capability IDs cannot be created dynamically from LLM-style or capability factory inputs.",
            )

        if capability_id in self._templates:
            raise CapabilityRegistryError(
                "DUPLICATE_CAPABILITY",
                f"Capability '{capability_id}' is already registered.",
            )

        self._templates[capability_id] = template.model_copy(deep=True)
        return self._templates[capability_id].model_copy(deep=True)

    def get(self, capability_id: str) -> CapabilityTemplateDefinition:
        if not isinstance(capability_id, str) or not capability_id.strip():
            raise CapabilityRegistryError(
                "CAPABILITY_NOT_FOUND",
                "A capability ID must be a non-empty string.",
            )

        template = self._templates.get(capability_id)
        if template is None:
            raise CapabilityRegistryError(
                "CAPABILITY_NOT_FOUND",
                f"Capability '{capability_id}' does not exist in the approved registry.",
            )
        return template.model_copy(deep=True)

    def has(self, capability_id: str) -> bool:
        return capability_id in self._templates

    def list(self) -> list[CapabilityTemplateDefinition]:
        return [template.model_copy(deep=True) for template in self._templates.values()]


__all__ = [
    "CapabilityRegistry",
    "CapabilityRegistryError",
]