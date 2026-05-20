from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel

from salesos_shared.ai_parsing import (
    AIStructuredError,
    extract_first_json_object,
    recover_structured_fields,
    validate_response_payload,
)
from salesos_shared.logging import get_logger, log_extra
from salesos_shared.retry import RetryError, retry_async


T = TypeVar("T", bound=BaseModel)
logger = get_logger(__name__)


class AIProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "ai_provider_error",
        details: list[AIStructuredError] | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or []
        self.diagnostics = diagnostics or {}


class AIResponseEnvelope(BaseModel):
    raw_text: str
    model: str
    attempts: int = 1


class AIProvider(ABC):
    @abstractmethod
    async def generate_text(self, *, model: str, prompt: str, temperature: float = 0.1) -> AIResponseEnvelope:
        raise NotImplementedError


class OllamaProvider(AIProvider):
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 60.0,
        retries: int = 3,
        keep_alive: str = "5m",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.keep_alive = keep_alive

    async def generate_text(self, *, model: str, prompt: str, temperature: float = 0.1) -> AIResponseEnvelope:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": temperature},
        }
        attempt_count = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async def perform_request() -> AIResponseEnvelope:
                nonlocal attempt_count
                attempt_count += 1
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                return AIResponseEnvelope(raw_text=data.get("response", ""), model=model, attempts=attempt_count)

            def on_retry(attempt: int, exc: BaseException) -> None:
                logger.warning(
                    "Ollama request retry",
                    extra=log_extra(model=model, retry_attempt=attempt, error=str(exc)),
                )

            try:
                return await retry_async(
                    perform_request,
                    attempts=self.retries,
                    timeout_seconds=self.timeout,
                    retry_exceptions=(httpx.HTTPError, httpx.TimeoutException, ValueError),
                    on_retry=on_retry,
                    retry_context={
                        "service": "ollama",
                        "retry_operation": "ollama_generate_text",
                        "model": model,
                    },
                )
            except RetryError as exc:
                diagnostics = {
                    "model": model,
                    "retry_attempts": max(attempt_count - 1, 0),
                    "failure_stage": "provider_request",
                }
                logger.warning(
                    "Ollama request failed after retries",
                    extra=log_extra(model=model, retry_attempts=diagnostics["retry_attempts"], error=str(exc)),
                )
                raise AIProviderError(
                    f"Ollama request failed after retries: {exc}",
                    code="provider_request_failed",
                    details=[
                        AIStructuredError(
                            code="provider_request_failed",
                            message="Ollama request failed after retry exhaustion.",
                            actual=str(exc),
                        )
                    ],
                    diagnostics=diagnostics,
                ) from exc

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [item.get("name", "") for item in data.get("models", [])]

    async def warmup_model(self, model: str) -> None:
        await self.generate_text(model=model, prompt="{}", temperature=0.0)


class JSONModelGenerator(Generic[T]):
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        response_model: type[T],
        temperature: float = 0.1,
        prompt_template: str = "default",
    ) -> T:
        logger.info(
            "Generating structured AI response",
            extra=log_extra(model=model, prompt_template=prompt_template, temperature=temperature),
        )
        envelope = await self.provider.generate_text(
            model=model,
            prompt=prompt,
            temperature=temperature,
        )
        diagnostics = {
            "model": envelope.model,
            "retry_attempts": max(envelope.attempts - 1, 0),
            "raw_length": len(envelope.raw_text),
            "prompt_template": prompt_template,
        }

        extraction = extract_first_json_object(envelope.raw_text)
        if extraction.payload is None:
            recovered_payload = self._recover_payload(envelope.raw_text, response_model)
            if recovered_payload is not None:
                logger.warning(
                    "Recovered structured fields from malformed Ollama response",
                    extra=log_extra(
                        model=model,
                        prompt_template=prompt_template,
                        retry_attempts=diagnostics["retry_attempts"],
                        recovered_fields=list(recovered_payload.keys()),
                        fallback_used=True,
                    ),
                )
                recovery_validation = validate_response_payload(recovered_payload, response_model)
                if recovery_validation.value is not None:
                    return recovery_validation.value
            diagnostics["failure_stage"] = "json_extraction"
            self._log_parsing_failure(
                "Ollama response JSON extraction failed",
                diagnostics=diagnostics,
                errors=extraction.errors,
                raw_text=envelope.raw_text,
            )
            raise AIProviderError(
                "Model response did not contain a valid JSON object.",
                code="json_extraction_failed",
                details=extraction.errors,
                diagnostics=diagnostics,
            )

        validation = validate_response_payload(extraction.payload, response_model)
        if validation.value is None:
            recovered_payload = self._recover_payload(envelope.raw_text, response_model)
            if recovered_payload is not None:
                logger.warning(
                    "Recovered structured fields after validation failure",
                    extra=log_extra(
                        model=model,
                        prompt_template=prompt_template,
                        retry_attempts=diagnostics["retry_attempts"],
                        recovered_fields=list(recovered_payload.keys()),
                        fallback_used=True,
                    ),
                )
                recovery_validation = validate_response_payload(recovered_payload, response_model)
                if recovery_validation.value is not None:
                    return recovery_validation.value
            diagnostics["failure_stage"] = "response_validation"
            diagnostics["extracted_json"] = extraction.json_text
            self._log_parsing_failure(
                "Ollama response validation failed",
                diagnostics=diagnostics,
                errors=validation.errors,
                raw_text=envelope.raw_text,
            )
            raise AIProviderError(
                "Model returned invalid structured data.",
                code="response_validation_failed",
                details=validation.errors,
                diagnostics=diagnostics,
            )

        return validation.value

    @staticmethod
    def _recover_payload(raw_text: str, response_model: type[T]) -> dict[str, Any] | None:
        field_names = list(response_model.model_fields.keys())
        recovered = recover_structured_fields(raw_text, field_names)
        if not recovered:
            return None

        for field_name, field_info in response_model.model_fields.items():
            if field_name not in recovered:
                continue
            annotation = field_info.annotation
            value = recovered[field_name]
            if annotation in {float, float | None}:
                try:
                    recovered[field_name] = float(str(value).strip())
                except ValueError:
                    continue
            elif annotation in {int, int | None}:
                try:
                    recovered[field_name] = int(str(value).strip())
                except ValueError:
                    continue
        return recovered

    @staticmethod
    def _log_parsing_failure(
        message: str,
        *,
        diagnostics: dict[str, Any],
        errors: list[AIStructuredError],
        raw_text: str,
    ) -> None:
        logger.warning(
            message,
            extra=log_extra(
                **diagnostics,
                errors=[error.model_dump() for error in errors],
                raw_preview=raw_text[:500],
            ),
        )
