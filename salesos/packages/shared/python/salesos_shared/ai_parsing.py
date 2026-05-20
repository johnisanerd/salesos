from __future__ import annotations

import json
import re
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, ValidationError


T = TypeVar("T", bound=BaseModel)

_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:json)?", re.IGNORECASE)


class AIStructuredError(BaseModel):
    code: str
    message: str
    field: str | None = None
    expected: str | None = None
    actual: str | None = None


class JSONExtractionResult(BaseModel):
    cleaned_text: str
    json_text: str | None = None
    payload: dict[str, Any] | None = None
    errors: list[AIStructuredError] = Field(default_factory=list)


class ValidationResult(BaseModel, Generic[T]):
    value: T | None = None
    errors: list[AIStructuredError] = Field(default_factory=list)


def strip_markdown_fences(raw_text: str) -> str:
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text)
    cleaned = cleaned.replace("```", "")
    return cleaned.strip()


def extract_first_json_object(raw_text: str) -> JSONExtractionResult:
    cleaned = strip_markdown_fences(raw_text)
    errors: list[AIStructuredError] = []

    for start_index, char in enumerate(cleaned):
        if char != "{":
            continue

        candidate = _slice_balanced_json_object(cleaned, start_index)
        if candidate is None:
            continue

        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            errors.append(
                AIStructuredError(
                    code="malformed_json",
                    message=f"Failed to decode candidate JSON object: {exc.msg}",
                    actual=candidate[:240],
                )
            )
            continue

        if isinstance(payload, dict):
            return JSONExtractionResult(
                cleaned_text=cleaned,
                json_text=candidate,
                payload=payload,
                errors=errors,
            )

        errors.append(
            AIStructuredError(
                code="json_not_object",
                message="Extracted JSON value was not an object.",
                actual=type(payload).__name__,
            )
        )

    errors.append(
        AIStructuredError(
            code="json_object_not_found",
            message="No valid JSON object was found in the model response.",
            actual=cleaned[:240],
        )
    )
    return JSONExtractionResult(cleaned_text=cleaned, errors=errors)


def validate_response_payload(payload: dict[str, Any], response_model: type[T]) -> ValidationResult[T]:
    try:
        return ValidationResult(value=response_model.model_validate(payload))
    except ValidationError as exc:
        return ValidationResult(errors=_map_validation_errors(exc))


def recover_structured_fields(raw_text: str, field_names: list[str]) -> dict[str, Any]:
    cleaned = strip_markdown_fences(raw_text)
    recovered: dict[str, Any] = {}

    for field_name in field_names:
        patterns = [
            re.compile(rf'"{re.escape(field_name)}"\s*:\s*"(?P<value>(?:[^"\\]|\\.)*)"', re.IGNORECASE),
            re.compile(rf"{re.escape(field_name)}\s*:\s*(?P<value>[^\n]+)", re.IGNORECASE),
        ]
        for pattern in patterns:
            match = pattern.search(cleaned)
            if not match:
                continue
            value = match.group("value").strip().strip(",")
            if not value:
                continue
            recovered[field_name] = value.replace('\\"', '"')
            break

    return recovered


def _slice_balanced_json_object(text: str, start_index: int) -> str | None:
    depth = 0
    in_string = False
    escape = False

    for index in range(start_index, len(text)):
        char = text[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]

    return None


def _map_validation_errors(exc: ValidationError) -> list[AIStructuredError]:
    errors: list[AIStructuredError] = []

    for entry in exc.errors():
        location = ".".join(str(part) for part in entry.get("loc", ())) or None
        errors.append(
            AIStructuredError(
                code=entry.get("type", "validation_error"),
                message=entry.get("msg", "Validation error"),
                field=location,
                actual=_stringify_input(entry.get("input")),
            )
        )

    return errors


def _stringify_input(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return type(value).__name__
