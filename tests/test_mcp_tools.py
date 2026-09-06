from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters
from mcp.types import ImageContent, ResourceLink

from codex_mcp_system.config import Settings
from codex_mcp_system.image_service import ServiceImageResult
from codex_mcp_system.models import AccountStatus, ImagegenStatus, ImageResult
from codex_mcp_system.server import create_mcp_server, format_image_result


class FakeService:
    async def close(self) -> None:
        return None

    async def account_status(self) -> AccountStatus:
        return AccountStatus(
            ready=True,
            auth_mode="chatgpt",
            plan_type="plus",
            imagegen_available=True,
            api_billing_blocked=True,
            codex_version="codex-cli fake",
            message="pronto",
        )

    async def imagegen_status(self, *, run_non_consuming_probe: bool = False) -> ImagegenStatus:
        return ImagegenStatus(
            available=True if run_non_consuming_probe else "unknown",
            backend="CodexAppServerBackend",
            output_directory="/tmp/output",
            timeout_seconds=600,
            inline_enabled=True,
            inline_max_bytes=2_097_152,
            known_limitations=[],
            message="cota do Codex",
        )


@pytest.mark.asyncio
async def test_exactly_four_public_tools(tmp_path: Path) -> None:
    server = create_mcp_server(
        Settings(output_dir=tmp_path),
        service=FakeService(),  # type: ignore[arg-type]
    )
    assert {tool.name for tool in await server.list_tools()} == {
        "codex_account_status",
        "generate_image",
        "edit_image",
        "imagegen_status",
    }


@pytest.mark.asyncio
async def test_non_generating_tool_over_in_memory_mcp(tmp_path: Path) -> None:
    server = create_mcp_server(
        Settings(output_dir=tmp_path),
        service=FakeService(),  # type: ignore[arg-type]
    )
    async with Client(server) as client:
        tools = await client.list_tools()
        assert len(tools.tools) == 4
        result = await client.call_tool("imagegen_status", {"run_non_consuming_probe": True})
    assert result.is_error is False
    assert result.structured_content["available"] is True


def test_image_result_contains_structured_data_and_inline_image() -> None:
    metadata = ImageResult(
        message="ok",
        path="/tmp/image.png",
        filename="image.png",
        mime_type="image/png",
        width=1,
        height=1,
        size_bytes=3,
        backend="CodexAppServerBackend",
        quota_notice="cota",
        inline_included=True,
    )
    result = format_image_result(ServiceImageResult(metadata=metadata, inline_bytes=b"png"))
    assert result.structured_content["path"] == "/tmp/image.png"
    assert any(isinstance(block, ImageContent) for block in result.content)


@pytest.mark.asyncio
async def test_stdio_server_does_not_print_startup_logs_to_stdout(
    tmp_path: Path, fake_codex: Path
) -> None:
    environment = os.environ.copy()
    environment["CODEX_MCP_CODEX_BIN"] = str(fake_codex)
    environment["CODEX_MCP_OUTPUT_DIR"] = str(tmp_path)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "codex_mcp_system",
        "serve",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=environment,
    )
    assert process.stdin is not None
    process.stdin.close()
    await process.stdin.wait_closed()
    stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
    assert process.returncode == 0
    assert stdout == b""


async def test_generate_and_edit_over_stdio_with_fake_backend(
    tmp_path: Path, fake_codex: Path, png_file: Path
) -> None:
    output = tmp_path / "output with spaces"
    transport = StdioServerParameters(
        command=sys.executable,
        args=["-m", "codex_mcp_system", "serve"],
        env={
            "CODEX_MCP_CODEX_BIN": str(fake_codex),
            "CODEX_MCP_OUTPUT_DIR": str(output),
            "FAKE_CODEX_ARTIFACT": str(png_file),
        },
    )
    async with Client(transport) as client:
        generated = await client.call_tool("generate_image", {"prompt": "a red cube"})
        assert not generated.is_error
        assert generated.structured_content["width"] == 32
        assert await asyncio.to_thread(Path(generated.structured_content["path"]).is_file)
        assert any(isinstance(block, ImageContent) for block in generated.content)
        edited = await client.call_tool(
            "edit_image",
            {
                "prompt": "change only the background",
                "image_paths": [str(png_file)],
                "include_inline": False,
            },
        )
        assert not edited.is_error
        assert edited.structured_content["auth_mode"] == "chatgpt"
        link = next(block for block in edited.content if isinstance(block, ResourceLink))
        assert "%20" in str(link.uri)
