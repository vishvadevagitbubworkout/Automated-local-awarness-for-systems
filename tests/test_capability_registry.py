import pytest

from app.capabilities.registry import CapabilityRegistry, CapabilityRegistryError
from app.capabilities.resolver import CapabilityResolver
from app.capabilities.security import CapabilitySecurityValidator
from app.capabilities.templates import (
    APPROVED_CAPABILITY_TEMPLATES,
    FILE_CREATE,
    FILE_DELETE,
    FILE_READ,
    FILE_WRITE,
    CapabilityTemplateDefinition,
    ResourceType,
    RiskLevel,
)
from app.intent.schemas import IntentCheckResult
from app.planner.schemas import PlanStep
from app.planner.schemas import TaskPlan


def test_registry_loads_approved_templates():
    registry = CapabilityRegistry()

    assert registry.has("file.read")
    assert registry.has("file.create")
    assert registry.has("file.write")
    assert registry.has("file.delete")
    assert registry.get("file.read") == FILE_READ
    assert list(registry.list()) == APPROVED_CAPABILITY_TEMPLATES


def test_unknown_capability_returns_controlled_failure():
    registry = CapabilityRegistry()

    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        registry.get("file.format_disk")


def test_duplicate_capability_ids_are_rejected():
    registry = CapabilityRegistry()

    with pytest.raises(CapabilityRegistryError, match="DUPLICATE_CAPABILITY"):
        registry.register(FILE_READ)


def test_validated_file_read_intent_resolves_to_file_read():
    resolver = CapabilityResolver()
    step = PlanStep(
        step_id="step_001",
        agent="file_manager",
        operation="READ",
        resource="report.pdf",
        parameters={"mode": "read"},
        description="Read the report file.",
    )

    resolved = resolver.resolve_step(step)
    assert resolved.capability_id == "file.read"


def test_validated_file_create_intent_resolves_to_file_create():
    resolver = CapabilityResolver()
    step = PlanStep(
        step_id="step_002",
        agent="file_manager",
        operation="CREATE",
        resource="notes.txt",
        parameters={"mode": "create"},
        description="Create a notes file.",
    )

    assert resolver.resolve_step(step).capability_id == "file.create"


def test_validated_file_write_intent_resolves_to_file_write():
    resolver = CapabilityResolver()
    step = PlanStep(
        step_id="step_003",
        agent="file_manager",
        operation="WRITE",
        resource="notes.txt",
        parameters={"mode": "write"},
        description="Write content to the file.",
    )

    assert resolver.resolve_step(step).capability_id == "file.write"


def test_validated_file_delete_intent_resolves_to_file_delete():
    resolver = CapabilityResolver()
    step = PlanStep(
        step_id="step_004",
        agent="file_manager",
        operation="DELETE",
        resource="draft.txt",
        parameters={"mode": "delete"},
        description="Delete the draft file.",
    )

    assert resolver.resolve_step(step).capability_id == "file.delete"


def test_unknown_operation_does_not_create_a_capability():
    resolver = CapabilityResolver()

    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        resolver.resolve("FORMAT")


def test_operational_resolver_does_not_accept_bare_capability_ids():
    with pytest.raises(TypeError):
        CapabilityResolver().resolve("READ", capability_id="file.read")


def test_unregistered_planner_template_cannot_resolve_as_a_capability():
    step = PlanStep(
        step_id="step_008",
        agent="browser_agent",
        operation="BROWSER_OPEN",
        resource="example.com",
        template="BROWSER_OPEN",
        intent="BROWSER_OPEN",
        parameters={},
    )

    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        CapabilityResolver().resolve_step(step)


def test_invalid_resource_type_does_not_resolve_a_file_capability():
    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        CapabilityResolver().resolve("READ", resource="directory")


def test_ambiguous_input_does_not_silently_select_a_capability():
    registry = CapabilityRegistry(
        [
            FILE_READ,
            CapabilityTemplateDefinition(
                capability_id="custom.read",
                agent="file_manager",
                operation="READ",
                resource_type=ResourceType.FILE,
                parameters={"mode": "read"},
                risk_level=RiskLevel.LOW,
                description="A second read template.",
            ),
        ]
    )

    with pytest.raises(CapabilityRegistryError, match="AMBIGUOUS_CAPABILITY"):
        CapabilityResolver(registry).resolve("READ", resource="report.pdf")


def test_llm_style_capability_id_cannot_create_new_template():
    registry = CapabilityRegistry()

    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        registry.register(
            CapabilityTemplateDefinition(
                capability_id="llm.create_capability",
                agent="prompt_agent",
                operation="READ",
                resource_type=ResourceType.FILE,
                parameters={"mode": "read"},
                risk_level=RiskLevel.LOW,
                description="A malicious capability definition.",
            )
        )


def test_registry_does_not_execute_requested_operation():
    registry = CapabilityRegistry()

    capability = registry.get("file.read")
    assert not hasattr(capability, "execute")
    assert not hasattr(capability, "run")
    assert callable(getattr(capability, "model_dump", None))


def test_registered_template_cannot_be_modified_through_registry_result():
    registry = CapabilityRegistry()
    returned = registry.get("file.read")
    returned.parameters["mode"] = "delete"

    assert registry.get("file.read").parameters == {"mode": "read"}


def test_security_validator_accepts_exact_registered_capability():
    registry = CapabilityRegistry()
    validator = CapabilitySecurityValidator(registry)

    approved = validator.validate(registry.get("file.read"))

    assert approved.capability_id == "file.read"
    assert approved.operation == "READ"


def test_security_validator_rejects_altered_capability():
    registry = CapabilityRegistry()
    altered = registry.get("file.read")
    altered.operation = "DELETE"

    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        CapabilitySecurityValidator(registry).validate(altered)


def test_security_validator_rejects_extra_privileged_parameters():
    registry = CapabilityRegistry()
    altered = registry.get("file.read")
    altered.parameters["execute"] = True

    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        CapabilitySecurityValidator(registry).validate(altered)


def test_security_validator_rejects_step_operation_escalation():
    registry = CapabilityRegistry()
    capability = registry.get("file.read")
    escalated_step = PlanStep(
        step_id="step_005",
        agent="file_manager",
        operation="DELETE",
        resource="report.pdf",
        parameters={"mode": "read"},
    )

    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        CapabilitySecurityValidator(registry).validate(capability, step=escalated_step)


def test_security_validator_rejects_mismatched_declared_template():
    capability = CapabilityRegistry().get("file.delete")
    step = PlanStep(
        step_id="step_007",
        agent="file_manager",
        operation="DELETE",
        resource="draft.txt",
        template="FILE_READ",
        parameters={"mode": "delete"},
    )

    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        CapabilitySecurityValidator().validate(capability, step=step)


def test_security_validator_rejects_invalid_resource_type():
    registry = CapabilityRegistry()
    altered = registry.get("file.read")
    altered.resource_type = ResourceType.DIRECTORY

    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        CapabilitySecurityValidator(registry).validate(altered)


def test_clarification_step_does_not_resolve_to_approved_capability():
    step = PlanStep(
        step_id="step_006",
        agent="planner_agent",
        operation="CLARIFY",
        intent="ASK_CLARIFICATION",
    )

    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        CapabilityResolver().resolve_step(step)


def test_validated_m2_plan_resolves_through_m3():
    plan = TaskPlan(
        task_id="task_001",
        original_request="Read report.pdf",
        steps=[
            PlanStep(
                step_id="step_001",
                agent="file_manager",
                operation="READ",
                resource="report.pdf",
                template="FILE_READ",
                intent="READ",
                parameters={"mode": "read"},
            )
        ],
    )
    result = IntentCheckResult(
        task_id="task_001",
        consistent=True,
        reason="The plan matches the request.",
        mismatched_steps=[],
    )

    capabilities = CapabilityResolver().resolve_validated_plan(plan, result)

    assert [capability.capability_id for capability in capabilities] == ["file.read"]


def test_inconsistent_m2_plan_cannot_produce_approved_capabilities():
    plan = TaskPlan(
        task_id="task_001",
        original_request="Read report.pdf",
        steps=[
            PlanStep(
                step_id="step_001",
                agent="file_manager",
                operation="READ",
                resource="report.pdf",
                parameters={"mode": "read"},
            )
        ],
    )
    result = IntentCheckResult(
        task_id="task_001",
        consistent=False,
        reason="The request is inconsistent.",
        mismatched_steps=["step_001"],
    )

    with pytest.raises(CapabilityRegistryError, match="CAPABILITY_NOT_FOUND"):
        CapabilityResolver().resolve_validated_plan(plan, result)
