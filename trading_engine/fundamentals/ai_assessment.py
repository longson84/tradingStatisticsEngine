"""AI assessment for growth fundamentals."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any

import httpx


class GrowthAssessmentConfigError(ValueError):
    """The local AI assessment configuration is missing or invalid."""


class GrowthAssessmentProviderError(RuntimeError):
    """The AI provider failed or returned an unusable response."""


class GrowthAssessmentEmptyResponse(GrowthAssessmentProviderError):
    """The AI provider returned a successful response with no usable text."""


@dataclass
class GrowthAssessment:
    provider: str
    model: str
    good_things: list[str]
    bad_things: list[str]
    risks: list[str]
    opportunities: list[str]
    investment_considerations: list[str]
    disclaimer: str
    prompt: str


def assess_growth_numbers(growth_payload: Any) -> GrowthAssessment:
    """Call an OpenAI-compatible model to assess growth fundamentals."""
    _load_env_file()
    api_key = os.environ.get("AI_ASSESSMENT_API_KEY")
    model = os.environ.get("AI_ASSESSMENT_MODEL")
    base_url = os.environ.get("AI_ASSESSMENT_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    response_format = os.environ.get("AI_ASSESSMENT_RESPONSE_FORMAT", "json_object")
    timeout_seconds = _env_float("AI_ASSESSMENT_TIMEOUT_SECONDS", 120.0)
    max_tokens = _env_int("AI_ASSESSMENT_MAX_TOKENS", 4096)

    if not api_key:
        raise GrowthAssessmentConfigError("AI_ASSESSMENT_API_KEY is not configured in .env")
    if not model:
        raise GrowthAssessmentConfigError("AI_ASSESSMENT_MODEL is not configured in .env")

    payload = _compact_growth_payload(growth_payload)
    prompt = _assessment_prompt(payload)
    request_body = _request_body(model, prompt, response_format, max_tokens)
    response = _post_chat_completion(base_url, api_key, request_body, timeout_seconds)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if response_format and response_format.lower() not in {"none", "false", "off"}:
            request_body = _request_body(model, prompt, "none", max_tokens)
            response = _post_chat_completion(base_url, api_key, request_body, timeout_seconds)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as retry_exc:
                raise GrowthAssessmentProviderError(_provider_error_message(retry_exc.response)) from retry_exc
        else:
            raise GrowthAssessmentProviderError(_provider_error_message(exc.response)) from exc

    try:
        content = _message_content(response)
    except GrowthAssessmentEmptyResponse:
        if response_format and response_format.lower() not in {"none", "false", "off"}:
            request_body = _request_body(model, prompt, "none", max_tokens)
            response = _post_chat_completion(base_url, api_key, request_body, timeout_seconds)
            response.raise_for_status()
            content = _message_content(response)
        else:
            raise
    parsed = _parse_json_object(content)
    return GrowthAssessment(
        provider="openai-compatible",
        model=model,
        good_things=_string_list(parsed.get("good_things")),
        bad_things=_string_list(parsed.get("bad_things")),
        risks=_string_list(parsed.get("risks")),
        opportunities=_string_list(parsed.get("opportunities")),
        investment_considerations=_string_list(parsed.get("investment_considerations")),
        disclaimer=str(parsed.get("disclaimer") or "Assessment is based only on the supplied historical numbers."),
        prompt=prompt,
    )


def _request_body(model: str, prompt: str, response_format: str, max_tokens: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a disciplined equity analyst. Assess only the numbers provided. "
                    "Do not invent news, valuation, products, management commentary, or forecasts. "
                    "Write for an individual investor deciding what to pay attention to before buying. "
                    "This is not financial advice. Return strict JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }
    if response_format.lower() not in {"none", "false", "off"}:
        body["response_format"] = {"type": response_format}
    return body


def _post_chat_completion(base_url: str, api_key: str, body: dict[str, Any], timeout_seconds: float) -> httpx.Response:
    return httpx.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=timeout_seconds,
    )


def _message_content(response: httpx.Response) -> str:
    try:
        body = response.json()
        choice = body["choices"][0]
        message = choice.get("message", {})
    except (KeyError, IndexError, TypeError) as exc:
        raise GrowthAssessmentProviderError("AI provider response did not match the expected chat/completions shape") from exc

    content = _content_to_text(message.get("content"))
    if not content:
        content = _content_to_text(choice.get("text"))
    if content:
        return content

    finish_reason = choice.get("finish_reason")
    message_keys = sorted(message.keys()) if isinstance(message, dict) else []
    if finish_reason == "length":
        raise GrowthAssessmentEmptyResponse(
            "AI provider returned an empty assessment because the response hit the token limit. "
            "Increase AI_ASSESSMENT_MAX_TOKENS."
        )
    raise GrowthAssessmentEmptyResponse(
        "AI provider returned an empty assessment "
        f"(finish_reason={finish_reason!r}, message_keys={message_keys})"
    )


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("output_text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part.strip() for part in parts if part.strip()).strip()
    return ""


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        text = text.removesuffix("```").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise GrowthAssessmentProviderError(f"AI provider did not return JSON. First 240 chars: {text[:240]}") from None
        try:
            parsed = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise GrowthAssessmentProviderError(f"AI provider returned invalid JSON. First 240 chars: {text[:240]}") from exc
    if not isinstance(parsed, dict):
        raise GrowthAssessmentProviderError("AI provider returned JSON, but not a JSON object")
    return parsed


def _provider_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except json.JSONDecodeError:
        return f"AI provider error {response.status_code}: {response.text[:240]}"
    detail = body.get("error", body)
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("detail") or json.dumps(detail, ensure_ascii=False)
    else:
        message = str(detail)
    return f"AI provider error {response.status_code}: {message}"


def _assessment_prompt(payload: dict[str, Any]) -> str:
    return (
        "Assess this company's growth quality from the supplied fundamental metrics.\n\n"
        "Required JSON shape:\n"
        "{\n"
        '  "good_things": ["..."],\n'
        '  "bad_things": ["..."],\n'
        '  "risks": ["..."],\n'
        '  "opportunities": ["..."],\n'
        '  "investment_considerations": ["..."],\n'
        '  "disclaimer": "One sentence saying this is based only on historical numbers and is not financial advice."\n'
        "}\n\n"
        "Rules:\n"
        "- Use 3 to 6 concise bullets in each list.\n"
        "- Tie every point to the numbers provided.\n"
        "- Mention uncertainty when data is missing, volatile, or inconsistent.\n"
        "- Focus on growth durability, margin leverage, cash conversion, EPS quality, share count, and quarterly momentum.\n"
        "- Do not recommend buy/sell/hold.\n\n"
        f"Data:\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
    )


def _compact_growth_payload(growth_payload: Any) -> dict[str, Any]:
    raw = asdict(growth_payload) if hasattr(growth_payload, "__dataclass_fields__") else growth_payload
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump(mode="json")
    if not isinstance(raw, dict):
        raise ValueError("growth_payload must be a mapping or dataclass")

    return {
        "symbol": raw.get("symbol"),
        "entity_name": raw.get("entity_name"),
        "requested_current_year": raw.get("requested_current_year"),
        "first_year": raw.get("first_year"),
        "last_year": raw.get("last_year"),
        "summary": raw.get("summary"),
        "annual_metrics": raw.get("annual_metrics"),
        "quarterly_metrics": raw.get("quarterly_metrics"),
        "recent_annual_rows": (raw.get("annual_rows") or [])[-10:],
        "recent_quarterly_rows": (raw.get("quarterly_rows") or [])[-12:],
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _load_env_file() -> None:
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and (key.startswith("AI_ASSESSMENT_") or key not in os.environ):
            os.environ[key] = value


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        raise GrowthAssessmentConfigError(f"{name} must be a number") from None


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise GrowthAssessmentConfigError(f"{name} must be an integer") from None
