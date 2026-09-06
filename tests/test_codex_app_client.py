from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from codex_mcp_system.codex_app_client import (
    CodexAppClient,
    compact_notification,
    extract_image_artifact,
    redact_diagnostic,
)
from codex_mcp_system.config import Settings
from codex_mcp_system.errors import (
    APIKeyAuthenticationBlockedError,
    AppServerProtocolError,
    GenerationTimeoutError,
    UsageLimitError,
)


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
        stats = await client.request("test/stats", {})
        assert stats["threads"][0]["config"]["features.shell_tool"] is False
        assert stats["threads"][0]["config"]["features.unified_exec"] is False
        assert stats["threads"][0]["modelProvider"] == "openai"
        assert stats["threads"][0]["allowProviderModelFallback"] is False
        assert stats["methods"].count("thread/unsubscribe") == 1
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
        stats = await client.request("test/stats", {})
        assert stats["methods"].count("turn/start") == 1
        assert stats["methods"].count("turn/interrupt") == 1
        assert stats["methods"].count("thread/unsubscribe") == 1


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
    text = redact_diagnostic(
        "Bearer abc123 user@example.com https://x.test/oauth?a=secret "
        "12345678-1234-1234-1234-123456789abc thr_secret turn_secret"
    )
    assert "abc123" not in text
    assert "user@example.com" not in text
    assert "a=secret" not in text
    assert "12345678" not in text
    assert "thr_secret" not in text
    assert "turn_secret" not in text


async def wait_for_turn(client: CodexAppClient) -> None:
    async with asyncio.timeout(5):
        while True:
            stats = await client.request("test/stats", {})
            if "turn/start" in stats["methods"]:
                return
            await asyncio.sleep(0.01)


async def test_cancellation_interrupts_and_releases_thread(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_TURN_MODE", "timeout")
    async with CodexAppClient(settings) as client:
        task = asyncio.create_task(client.run_image_turn(prompt="$imagegen test", cwd=tmp_path))
        await wait_for_turn(client)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        stats = await client.request("test/stats", {})
        assert stats["methods"].count("turn/start") == 1
        assert stats["methods"].count("turn/interrupt") == 1
        assert stats["methods"].count("thread/unsubscribe") == 1
        assert not client._turn_backlog
        assert not client._turn_queues


async def test_queued_job_rechecks_authentication(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_TURN_MODE", "timeout")
    async with CodexAppClient(settings) as client:
        first = asyncio.create_task(client.run_image_turn(prompt="$imagegen first", cwd=tmp_path))
        await wait_for_turn(client)
        second = asyncio.create_task(client.run_image_turn(prompt="$imagegen next", cwd=tmp_path))
        await client.request("test/set-auth", {"authMode": "apiKey"})
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        with pytest.raises(APIKeyAuthenticationBlockedError):
            await second
        stats = await client.request("test/stats", {})
        assert stats["methods"].count("turn/start") == 1
        assert stats["methods"].count("thread/unsubscribe") == 2


async def test_authentication_is_checked_after_thread_creation(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_AUTH_ON_THREAD_START", "apiKey")
    async with CodexAppClient(settings) as client:
        assert (await client.account_read()).auth_mode == "chatgpt"
        with pytest.raises(APIKeyAuthenticationBlockedError):
            await client.run_image_turn(prompt="$imagegen test", cwd=tmp_path)
        assert "turn/start" not in (await client.request("test/stats", {}))["methods"]


async def test_concurrent_requests_wait_for_initialization(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_INIT_DELAY", "0.1")
    async with asyncio.timeout(5):
        client = CodexAppClient(settings)
        try:
            accounts = await asyncio.gather(*(client.account_read() for _ in range(4)))
            assert all(account.auth_mode == "chatgpt" for account in accounts)
            assert (await client.request("test/stats", {}))["methods"].count("initialize") == 1
        finally:
            await client.shutdown()


async def test_reader_failure_restarts_only_for_a_new_request(settings: Settings) -> None:
    async with CodexAppClient(settings) as client:
        original = client.process
        with pytest.raises(AppServerProtocolError, match="JSONL inválida"):
            await client.request("test/malformed", {})
        assert not client.running
        assert (await client.account_read()).auth_mode == "chatgpt"
        assert client.process is not original
        assert original is not None and original.returncode is not None


async def test_non_object_response_is_rejected(settings: Settings) -> None:
    async with CodexAppClient(settings) as client:
        with pytest.raises(AppServerProtocolError, match="não é um objeto"):
            await client.request("test/invalid-result", {})


async def test_lost_turn_start_response_stops_child_without_retry(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_TURN_MODE", "lost_start")
    async with CodexAppClient(replace(settings, timeout_seconds=0.1)) as client:
        original = client.process
        with pytest.raises(GenerationTimeoutError):
            await client.run_image_turn(prompt="$imagegen test", cwd=tmp_path)
        assert client.process is None
        assert original is not None and original.returncode is not None


async def test_process_exit_during_generation_fails_without_retry(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_TURN_MODE", "exit_after_start")
    async with CodexAppClient(settings) as client:
        async with asyncio.timeout(5):
            with pytest.raises(AppServerProtocolError):
                await client.run_image_turn(prompt="$imagegen test", cwd=tmp_path)
        assert client.process is None


async def test_interrupt_ack_without_completion_stops_child(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_TURN_MODE", "interrupt_stuck")
    async with CodexAppClient(replace(settings, timeout_seconds=0.1)) as client:
        original = client.process
        with pytest.raises(GenerationTimeoutError):
            await client.run_image_turn(prompt="$imagegen test", cwd=tmp_path)
        assert client.process is None
        assert original is not None and original.returncode is not None
