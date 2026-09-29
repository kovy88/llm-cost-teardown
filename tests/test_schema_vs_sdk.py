"""Field names the loaders read must exist in the official SDK types (CLAUDE.md rule)."""

import json

import pytest
from anthropic.types import Usage as AnthropicUsage
from openai.types.admin.organization.usage_completions_response import (
    DataResultOrganizationCostsResult,
    DataResultOrganizationCostsResultAmount,
    DataResultOrganizationUsageCompletionsResult,
    UsageCompletionsResponse,
)
from openai.types.admin.organization.usage_costs_response import UsageCostsResponse
from openai.types.completion_usage import CompletionTokensDetails, CompletionUsage, PromptTokensDetails
from openai.types.responses.response_usage import InputTokensDetails, OutputTokensDetails, ResponseUsage

from llm_cost_teardown.samples import write_samples
from llm_cost_teardown.usage import _usage_from_sdk

OPENAI_USAGE_FIELDS = {
    "input_tokens",
    "input_cached_tokens",
    "input_cache_write_tokens",
    "input_uncached_tokens",
    "output_tokens",
    "num_model_requests",
    "project_id",
    "api_key_id",
    "user_id",
    "model",
    "batch",
    "service_tier",
}


def test_openai_usage_result_fields_exist():
    assert OPENAI_USAGE_FIELDS <= set(DataResultOrganizationUsageCompletionsResult.model_fields)


def test_openai_cost_result_fields_exist():
    assert {"amount", "line_item", "project_id"} <= set(DataResultOrganizationCostsResult.model_fields)
    assert {"value", "currency"} <= set(DataResultOrganizationCostsResultAmount.model_fields)


def test_request_usage_fields_exist():
    assert {"prompt_tokens", "completion_tokens", "prompt_tokens_details", "completion_tokens_details"} <= set(
        CompletionUsage.model_fields
    )
    assert {"cached_tokens", "cache_write_tokens"} <= set(PromptTokensDetails.model_fields)
    assert "reasoning_tokens" in CompletionTokensDetails.model_fields
    assert {"input_tokens", "output_tokens", "input_tokens_details", "output_tokens_details"} <= set(
        ResponseUsage.model_fields
    )
    assert {"cached_tokens", "cache_write_tokens"} <= set(InputTokensDetails.model_fields)
    assert "reasoning_tokens" in OutputTokensDetails.model_fields
    assert {
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "cache_creation",
        "server_tool_use",
        "output_tokens_details",
        "service_tier",
        "inference_geo",
    } <= set(AnthropicUsage.model_fields)


def test_chat_completions_usage_roundtrip():
    usage = CompletionUsage(
        prompt_tokens=5000,
        completion_tokens=300,
        total_tokens=5300,
        prompt_tokens_details=PromptTokensDetails(cached_tokens=3072, cache_write_tokens=512),
        completion_tokens_details=CompletionTokensDetails(reasoning_tokens=100),
    )
    tokens = _usage_from_sdk(usage.model_dump(), "openai")
    assert tokens["uncached_input_tokens"] == 5000 - 3072 - 512
    assert tokens["cache_read_tokens"] == 3072
    assert tokens["cache_write_tokens"] == 512
    assert tokens["reasoning_tokens"] == 100


def test_responses_usage_roundtrip():
    usage = ResponseUsage(
        input_tokens=4000,
        input_tokens_details=InputTokensDetails(cached_tokens=2048, cache_write_tokens=0),
        output_tokens=250,
        output_tokens_details=OutputTokensDetails(reasoning_tokens=50),
        total_tokens=4250,
    )
    tokens = _usage_from_sdk(usage.model_dump(), "openai")
    assert tokens["uncached_input_tokens"] == 1952
    assert tokens["output_tokens"] == 250


def test_anthropic_usage_roundtrip():
    usage = AnthropicUsage.model_validate(
        {
            "input_tokens": 200,
            "output_tokens": 400,
            "cache_read_input_tokens": 6000,
            "cache_creation_input_tokens": 1500,
            "cache_creation": {"ephemeral_5m_input_tokens": 1000, "ephemeral_1h_input_tokens": 500},
        }
    )
    tokens = _usage_from_sdk(usage.model_dump(), "anthropic")
    # Anthropic input_tokens already excludes cache reads and writes.
    assert tokens["uncached_input_tokens"] == 200
    assert tokens["cache_read_tokens"] == 6000
    assert tokens["cache_write_tokens"] == 1000
    assert tokens["cache_write_1h_tokens"] == 500


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    out = tmp_path_factory.mktemp("samples")
    write_samples(out)
    return out


def test_synthetic_openai_export_validates_against_sdk(samples):
    for page in json.loads((samples / "openai_usage.json").read_text()):
        UsageCompletionsResponse.model_validate(page)


def test_synthetic_openai_costs_validate_against_sdk(samples):
    UsageCostsResponse.model_validate(json.loads((samples / "openai_costs.json").read_text()))


def test_synthetic_request_usage_validates_against_sdk(samples):
    for line in (samples / "requests_raw_small.jsonl").read_text().splitlines():
        record = json.loads(line)
        if record["vendor"] == "openai":
            CompletionUsage.model_validate(record["usage"])
        else:
            AnthropicUsage.model_validate(record["usage"])
