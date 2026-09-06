from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from codex_mcp_system.codex_app_client import (
    CodexAppClient,
    compact_notification,
    extract_image_artifact,
    redact_diagnostic,
)
from codex_mcp_system.config import Settings
from codex_mcp_system.errors import GenerationTimeoutError, UsageLimitError


@pytest.mark.asyncio
async def test_initialization_correlation_account_and_shutdown(settings: Settings) -> None:
    client = CodexAppClient(settings)
    await client.ensure_started()
    process = client.process
    results = await asyncio.gather(
        client.request("test/echo", {"value": "a"}),
        client.request("test/echo", {"value": "b"}),
        client.request("test/echo", {"value": "c"}),
    )
    assert [result["value"] for result in results] == ["a", "b", "c"]
    account = await client.account_read()
    assert account.auth_mode == "chatgpt"
    assert account.plan_type == "plus"
    assert await client.imagegen_available(Path.cwd()) is True
    await client.shutdown()
    assert process is not None
    assert process.returncode == 0


@pytest.mark.asyncio
async def test_openai_key_is_not_forwarded(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "never-forward-this")
    async with CodexAppClient(settings) as client:
        result = await client.request("debug/env", {})
    assert result == {"hasOpenAIKey": False}


@pytest.mark.asyncio
async def test_large_jsonl_image_event_is_framed(
    settings: Settings, png_file: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_CODEX_ARTIFACT", str(png_file))
    async with CodexAppClient(settings) as client:
        artifact = await client.run_image_turn(prompt="$imagegen test", cwd=tmp_path)
    assert artifact.source_path == str(png_file)
    assert artifact.status == "completed"


@pytest.mark.asyncio
async def test_turn_timeout_interrupts_without_retry(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_TURN_MODE", "timeout")
    quick = Settings(
        output_dir=settings.output_dir,
        codex_bin=settings.codex_bin,
        timeout_seconds=0.05,
    )
    async with CodexAppClient(quick) as client:
        with pytest.raises(GenerationTimeoutError, match="não houve retry"):
            await client.run_image_turn(prompt="$imagegen test", cwd=tmp_path)


def test_extract_artifact_and_usage_limit() -> None:
    events = [
        {
            "method": "item/completed",
            "params": {
                "item": {
                    "type": "imageGeneration",
                    "status": "completed",
                    "savedPath": "/tmp/result.png",
                }
            },
        }
    ]
    assert extract_image_artifact(events).source_path == "/tmp/result.png"
    events[0]["params"]["item"] = {
        "type": "imageGeneration",
        "status": "failed",
        "failure": {"type": "usageLimitExceeded", "limitId": "secret-id"},
    }
    with pytest.raises(UsageLimitError):
        extract_image_artifact(events)


def test_compaction_drops_large_inline_result() -> None:
    compact = compact_notification(
        {
            "method": "item/completed",
            "params": {
                "turnId": "turn",
                "item": {
                    "type": "imageGeneration",
                    "status": "completed",
                    "result": "x" * 100_000,
                    "savedPath": "/tmp/result.png",
                },
            },
        }
    )
    assert "result" not in compact["params"]["item"]
    assert compact["params"]["item"]["savedPath"] == "/tmp/result.png"


def test_diagnostics_are_redacted() -> None:
    text = redact_diagnostic("Bearer abc123 user@example.com https://x.test/oauth?a=secret")
    assert "abc123" not in text
    assert "user@example.com" not in text
    assert "a=secret" not in text
