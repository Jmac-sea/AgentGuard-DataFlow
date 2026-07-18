from __future__ import annotations

import base64

from agentguard.dataflow import ArtifactRegistry, normalize_text

SECRET = "CANARY_SECRET_8F31A72"


def registry_with_secret() -> ArtifactRegistry:
    registry = ArtifactRegistry(session_id="ses_test", canaries={SECRET})
    registry.register_tool_result(
        call_id="call_read",
        tool_name="filesystem.read",
        arguments={"path": "/secrets/api_key.txt"},
        result=SECRET,
    )
    return registry


def test_normalize_text_removes_common_separators() -> None:
    assert normalize_text("Canary Secret-123") == "canarysecret123"


def test_exact_match() -> None:
    matches = registry_with_secret().match_arguments({"body": f"value={SECRET}"})
    assert matches[0].match_type == "exact_or_embedded"
    assert matches[0].confidence == 1.0


def test_base64_match() -> None:
    encoded = base64.b64encode(SECRET.encode()).decode()
    matches = registry_with_secret().match_arguments({"body": encoded})
    assert matches[0].match_type == "base64_decoded"
    assert matches[0].confidence == 0.96


def test_unrelated_text_does_not_match() -> None:
    matches = registry_with_secret().match_arguments({"body": "public customer report"})
    assert matches == []


def test_split_fields_are_recombined() -> None:
    midpoint = len(SECRET) // 2
    matches = registry_with_secret().match_arguments(
        {"title": SECRET[:midpoint], "body": SECRET[midpoint:]}
    )

    assert matches[0].match_type == "split_recombined"
    assert matches[0].confidence == 0.90
