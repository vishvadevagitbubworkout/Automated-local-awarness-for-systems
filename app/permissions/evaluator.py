from __future__ import annotations

from app.capabilities.registry import CapabilityRegistry
from app.capabilities.security import CapabilitySecurityValidator
from app.capabilities.templates import CapabilityTemplateDefinition
from app.permissions.policies import (
    PermissionDecision,
    PermissionPolicyRegistry,
    PermissionScope,
)


class PermissionEvaluator:
    """Deterministically evaluate an approved capability against policy."""

    def __init__(
        self,
        policy_registry: PermissionPolicyRegistry | None = None,
        capability_registry: CapabilityRegistry | None = None,
    ):
        self.policy_registry = policy_registry or PermissionPolicyRegistry()
        self.capability_registry = capability_registry or CapabilityRegistry()
        self.capability_validator = CapabilitySecurityValidator(self.capability_registry)

    def evaluate(
        self,
        capability: CapabilityTemplateDefinition,
        *,
        agent: str,
        operation: str,
        resource_type,
        scope: PermissionScope | None,
        parameters: dict | None = None,
    ) -> PermissionDecision:
        """Return ALLOW only when every authorization input matches policy."""
        try:
            canonical = self.capability_validator.validate(capability)
            matching_policies = [
                policy
                for policy in self.policy_registry.list()
                if policy.capability_id == canonical.capability_id
            ]
            if len(matching_policies) != 1:
                return PermissionDecision.DENY
            policy = matching_policies[0]
            requested_parameters = parameters if parameters is not None else {}

            if not isinstance(agent, str) or agent != canonical.agent:
                return PermissionDecision.DENY
            if not isinstance(operation, str) or operation.upper() != canonical.operation.upper():
                return PermissionDecision.DENY
            if resource_type != canonical.resource_type:
                return PermissionDecision.DENY
            if scope is None or not isinstance(scope, PermissionScope):
                return PermissionDecision.DENY
            if (
                scope.resource_type != policy.scope.resource_type
                or scope.kind != policy.scope.kind
                or scope.selector != policy.scope.selector
            ):
                return PermissionDecision.DENY
            if requested_parameters != canonical.parameters:
                return PermissionDecision.DENY
            if policy.operation.upper() != canonical.operation.upper():
                return PermissionDecision.DENY
            if policy.resource_type != canonical.resource_type:
                return PermissionDecision.DENY
            if policy.risk_level != canonical.risk_level:
                return PermissionDecision.DENY

            return policy.decision
        except (TypeError, ValueError, AttributeError):
            return PermissionDecision.DENY


__all__ = ["PermissionEvaluator"]
