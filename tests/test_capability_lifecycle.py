from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from app.security.capabilities import UsagePolicy
from app.security.key_provider import CapabilityKeyProvider
from app.security.lifecycle import (
    CapabilityExpiredError,
    CapabilityLifecycleState,
    CapabilityLifecycleStore,
    CapabilityReplayError,
    CapabilityRevokedError,
    CapabilityStateError,
)
from app.security.minting import CapabilityMinter, CapabilityMintingPolicy
from app.security.verification import CapabilityVerifier
from tests.test_capability_minting import KEY, allowed, plan


def make_verified(*, usage_policy=UsagePolicy.ONE_TIME):
    task = plan()
    minter = CapabilityMinter(
        key_provider=CapabilityKeyProvider.for_testing(KEY),
        policy=CapabilityMintingPolicy(usage_policy=usage_policy),
    )
    authenticated = minter.mint(allowed(task), task, task.steps[0])
    return CapabilityVerifier(key_provider=CapabilityKeyProvider.for_testing(KEY)).verify(authenticated)


def test_one_time_capability_is_consumed_once():
    capability = make_verified()
    store = CapabilityLifecycleStore()

    assert store.state(capability) == CapabilityLifecycleState.ACTIVE
    assert store.verify_and_consume(capability) is capability
    assert store.state(capability) == CapabilityLifecycleState.USED

    with pytest.raises(CapabilityReplayError):
        store.verify_and_consume(capability)


def test_repeatable_capability_remains_usable_until_expiry():
    capability = make_verified(usage_policy=UsagePolicy.REPEATABLE)
    store = CapabilityLifecycleStore()

    store.check_usable(capability)
    store.verify_and_consume(capability)
    store.verify_and_consume(capability)

    assert store.state(capability) == CapabilityLifecycleState.ACTIVE


def test_expiry_is_enforced_without_changing_claims():
    capability = make_verified()
    store = CapabilityLifecycleStore()
    after_expiry = capability.claims.expires_at + timedelta(seconds=1)

    with pytest.raises(CapabilityExpiredError):
        store.check_usable(capability, now=after_expiry)
    assert store.state(capability, now=after_expiry) == CapabilityLifecycleState.EXPIRED
    assert capability.claims.expires_at < after_expiry


def test_revocation_rejects_future_use():
    capability = make_verified()
    store = CapabilityLifecycleStore()

    store.revoke(capability)
    assert store.state(capability) == CapabilityLifecycleState.REVOKED
    with pytest.raises(CapabilityRevokedError):
        store.check_usable(capability)
    with pytest.raises(CapabilityRevokedError):
        store.verify_and_consume(capability)


def test_invalid_lifecycle_transitions_fail_closed():
    used = make_verified()
    store = CapabilityLifecycleStore()
    store.verify_and_consume(used)
    with pytest.raises(CapabilityStateError):
        store.revoke(used)

    revoked = make_verified()
    store.revoke(revoked)
    with pytest.raises(CapabilityStateError):
        store.revoke(revoked)


def test_concurrent_one_time_consumption_allows_exactly_one_success():
    capability = make_verified()
    store = CapabilityLifecycleStore()

    def consume():
        try:
            store.verify_and_consume(capability)
            return True
        except CapabilityReplayError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: consume(), range(2)))

    assert results.count(True) == 1
    assert results.count(False) == 1
    assert store.state(capability) == CapabilityLifecycleState.USED


def test_unverified_capability_cannot_enter_lifecycle():
    authenticated = CapabilityMinter(
        key_provider=CapabilityKeyProvider.for_testing(KEY)
    ).mint(allowed(plan()), plan(), plan().steps[0])
    store = CapabilityLifecycleStore()

    with pytest.raises(CapabilityStateError):
        store.check_usable(authenticated)  # type: ignore[arg-type]


def test_lifecycle_does_not_add_execution_or_replay_reset_apis():
    store = CapabilityLifecycleStore()

    assert not hasattr(store, "execute")
    assert not hasattr(store, "reset")
    assert not hasattr(store, "verify_and_consume_again")
