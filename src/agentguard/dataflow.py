from __future__ import annotations

import base64
import binascii
import hashlib
import re
import unicodedata
from collections.abc import Iterable
from contextlib import suppress
from typing import Any
from uuid import uuid4

from agentguard.models import DataArtifact, ProvenanceMatch


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"[\s\-_.,:;/\\]+", "", normalized).casefold()


def flatten_strings(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from flatten_strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from flatten_strings(item, f"{path}[{index}]")


class ArtifactRegistry:
    def __init__(self, session_id: str, canaries: set[str]) -> None:
        self.session_id = session_id
        self.canaries = canaries
        self._artifacts: dict[str, tuple[DataArtifact, str]] = {}

    @property
    def artifacts(self) -> list[DataArtifact]:
        return [artifact for artifact, _ in self._artifacts.values()]

    def register_tool_result(
        self,
        *,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
    ) -> list[DataArtifact]:
        resource = self._resource_from_arguments(arguments)
        registered: list[DataArtifact] = []
        for _, text in flatten_strings(result):
            labels = self._classify(tool_name, resource, text)
            if "sensitivity:secret" not in labels:
                continue
            artifact = DataArtifact(
                artifact_id=f"art_{uuid4().hex[:12]}",
                session_id=self.session_id,
                source_call_id=call_id,
                source_tool=tool_name,
                resource=resource,
                labels=labels,
                length=len(text),
                sha256=hashlib.sha256(text.encode()).hexdigest(),
            )
            self._artifacts[artifact.artifact_id] = (artifact, text)
            registered.append(artifact)
        return registered

    def match_arguments(self, arguments: dict[str, Any]) -> list[ProvenanceMatch]:
        matches: list[ProvenanceMatch] = []
        fields = list(flatten_strings(arguments))
        individually_matched: set[str] = set()
        for target_path, target_text in fields:
            for artifact, raw_value in self._artifacts.values():
                result = self._match(raw_value, target_text)
                if result is None:
                    continue
                match_type, confidence = result
                if confidence >= 0.85:
                    individually_matched.add(artifact.artifact_id)
                matches.append(
                    ProvenanceMatch(
                        artifact_id=artifact.artifact_id,
                        source_tool=artifact.source_tool,
                        source_resource=artifact.resource,
                        target_path=target_path,
                        match_type=match_type,
                        confidence=confidence,
                        labels=artifact.labels,
                    )
                )

        if len(fields) > 1:
            combined = "".join(value for _, value in fields)
            for artifact, raw_value in self._artifacts.values():
                if artifact.artifact_id in individually_matched:
                    continue
                if normalize_text(raw_value) not in normalize_text(combined):
                    continue
                matches.append(
                    ProvenanceMatch(
                        artifact_id=artifact.artifact_id,
                        source_tool=artifact.source_tool,
                        source_resource=artifact.resource,
                        target_path="$::<combined>",
                        match_type="split_recombined",
                        confidence=0.90,
                        labels=artifact.labels,
                    )
                )
        return sorted(matches, key=lambda item: item.confidence, reverse=True)

    def clear(self) -> None:
        self._artifacts.clear()

    def _classify(self, tool_name: str, resource: str | None, text: str) -> set[str]:
        labels: set[str] = {f"source:{tool_name.split('.', maxsplit=1)[0]}"}
        secret_path = resource is not None and (
            resource.startswith("/secrets/") or resource.lower().endswith(".env")
        )
        contains_canary = any(canary in text for canary in self.canaries)
        if secret_path or contains_canary:
            labels.update({"sensitivity:secret", "handling:no_external_write"})
        return labels

    @staticmethod
    def _resource_from_arguments(arguments: dict[str, Any]) -> str | None:
        for key in ("path", "resource", "uri"):
            value = arguments.get(key)
            if isinstance(value, str):
                return value
        return None

    @staticmethod
    def _match(source: str, target: str) -> tuple[str, float] | None:
        if not source or not target:
            return None
        if source in target:
            return "exact_or_embedded", 1.0

        normalized_source = normalize_text(source)
        normalized_target = normalize_text(target)
        if len(normalized_source) >= 8 and normalized_source in normalized_target:
            return "normalized", 0.97

        for kind, candidate in ArtifactRegistry._decode_candidates(target):
            if source in candidate or normalize_text(source) in normalize_text(candidate):
                return kind, 0.96

        minimum = max(8, min(16, len(normalized_source) // 2))
        if len(normalized_source) >= minimum:
            for start in range(0, len(normalized_source) - minimum + 1):
                fragment = normalized_source[start : start + minimum]
                if fragment in normalized_target:
                    coverage = min(1.0, len(fragment) / len(normalized_source))
                    return "substring", max(0.75, coverage)
        return None

    @staticmethod
    def _decode_candidates(value: str) -> Iterable[tuple[str, str]]:
        compact = re.sub(r"\s+", "", value)
        base64_tokens = {compact}
        base64_pattern = r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{12,}={0,2}(?![A-Za-z0-9+/])"
        base64_tokens.update(re.findall(base64_pattern, value))
        for token in base64_tokens:
            if len(token) < 8:
                continue
            with suppress(binascii.Error, UnicodeDecodeError, ValueError):
                padding = "=" * (-len(token) % 4)
                decoded = base64.b64decode(token + padding, validate=True).decode("utf-8")
                yield "base64_decoded", decoded

        hex_tokens = {compact}
        hex_tokens.update(re.findall(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{16,}(?![0-9A-Fa-f])", value))
        for token in hex_tokens:
            if len(token) < 8 or len(token) % 2:
                continue
            with suppress(ValueError, UnicodeDecodeError):
                yield "hex_decoded", bytes.fromhex(token).decode("utf-8")
