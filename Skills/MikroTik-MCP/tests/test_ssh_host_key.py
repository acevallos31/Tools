from __future__ import annotations

import paramiko
import pytest

from mikrotik_skill.client import (
    PinnedHostKeyPolicy,
    SSHHostKeyMismatch,
    normalize_fingerprint,
    ssh_key_fingerprint_sha256,
)


def test_fingerprint_is_openssh_style() -> None:
    key = paramiko.RSAKey.generate(1024)
    fingerprint = ssh_key_fingerprint_sha256(key)

    assert fingerprint.startswith("SHA256:")
    assert "=" not in fingerprint


def test_normalize_fingerprint_accepts_prefix_or_raw_value() -> None:
    assert normalize_fingerprint("SHA256:abc=") == "SHA256:abc"
    assert normalize_fingerprint("abc=") == "SHA256:abc"


def test_pinned_policy_accepts_matching_key() -> None:
    key = paramiko.RSAKey.generate(1024)
    policy = PinnedHostKeyPolicy(
        ssh_key_fingerprint_sha256(key)
    )

    policy.missing_host_key(None, "router", key)  # type: ignore[arg-type]


def test_pinned_policy_rejects_mismatch() -> None:
    expected = paramiko.RSAKey.generate(1024)
    actual = paramiko.RSAKey.generate(1024)
    policy = PinnedHostKeyPolicy(
        ssh_key_fingerprint_sha256(expected)
    )

    with pytest.raises(SSHHostKeyMismatch) as exc_info:
        policy.missing_host_key(None, "router", actual)  # type: ignore[arg-type]

    assert exc_info.value.expected == ssh_key_fingerprint_sha256(expected)
    assert exc_info.value.actual == ssh_key_fingerprint_sha256(actual)
