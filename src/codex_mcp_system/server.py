from __future__ import annotations

import base64
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from mcp.server import MCPServer
from mcp.types import CallToolResult, ImageContent, ResourceLink, TextContent
from pydantic import Field

from codex_mcp_system import __version__
from codex_mcp_system.config import Settings
from codex_mcp_system.errors import CodexMCPError
from codex_mcp_system.image_service import ImageService, ServiceImageResult
from codex_mcp_system.models import Background, OutputFormat, Quality

logger = logging.getLogger(__name__)


def _error_result(exc: Exception) -> CallToolResult:
    if isinstance(exc, (CodexMCPError, ValueError)):
        message = str(exc)
    else:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Erro interno em ferramenta MCP")
        else:
            logger.error("Erro interno em ferramenta MCP: %s", type(exc).__name__)
        message = "Falha interna inesperada; consulte stderr com CODEX_MCP_LOG_LEVEL=DEBUG."
    return CallToolResult(content=[TextContent(text=message)], isError=True)


def format_image_result(result: ServiceImageResult) -> CallToolResult:
    structured = result.metadata.model_dump(mode="json")
    content: list[TextContent | ImageContent | ResourceLink] = [
        TextContent(text=json.dumps(structured, ensure_ascii=False, indent=2))
    ]
    if result.inline_bytes is not None:
        content.append(
            ImageContent(
                data=base64.b64encode(result.inline_bytes).decode("ascii"),
                mimeType=result.metadata.mime_type,
            )
        )
    else:
        content.append(
            ResourceLink(
                name=result.metadata.filename,
                uri=Path(result.metadata.path).as_uri(),
                mimeType=result.metadata.mime_type,
                size=result.metadata.size_bytes,
                description="Imagem local gerada pelo Codex.",
            )
        )
    return CallToolResult(content=content, structuredContent=structured)


def create_mcp_server(
    settings: Settings | None = None, *, service: ImageService | None = None
) -> MCPServer:
    active_settings = settings or Settings.from_env()
    active_service = service or ImageService(active_settings)

    @asynccontextmanager
    async def lifespan(_: MCPServer):
        try:
            yield {"service": active_service}
        finally:
            await active_service.close()

    server = MCPServer(
        "codex-mcp-system",
        title="Codex MCP System (não oficial)",
        description=(
            "Servidor MCP local e pessoal para a geração integrada de imagens do Codex "
            "autenticado com ChatGPT."
        ),
        version=__version__,
        log_level=active_settings.log_level,  # type: ignore[arg-type]
        lifespan=lifespan,
    )

    @server.tool(
        annotations={"readOnlyHint": True, "openWorldHint": False},
        structured_output=False,
    )
    async def codex_account_status() -> CallToolResult:
        """Verifica autenticação ChatGPT, plano, Codex e disponibilidade de $imagegen."""
        try:
            status = await active_service.account_status()
            structured = status.model_dump(mode="json")
            return CallToolResult(
                content=[TextContent(text=json.dumps(structured, ensure_ascii=False, indent=2))],
                structuredContent=structured,
            )
        except Exception as exc:
            return _error_result(exc)

    @server.tool(
        annotations={"readOnlyHint": False, "openWorldHint": False, "idempotentHint": False},
        structured_output=False,
    )
    async def generate_image(
        prompt: Annotated[str, Field(description="Descrição visual; máximo de 8000 caracteres")],
        size: Annotated[str, Field(description="auto ou WIDTHxHEIGHT compatível")] = "1024x1024",
        quality: Quality = "medium",
        background: Background = "auto",
        output_format: OutputFormat = "png",
        output_filename: Annotated[
            str | None, Field(description="Somente nome do arquivo, sem diretórios")
        ] = None,
        output_directory: Annotated[
            str | None,
            Field(description="Diretório local explícito; usa a configuração se omitido"),
        ] = None,
        include_inline: bool = True,
    ) -> CallToolResult:
        """Gera uma imagem com $imagegen e a cota do Codex da conta ChatGPT."""
        try:
            result = await active_service.generate_image(
                prompt=prompt,
                size=size,
                quality=quality,
                background=background,
                output_format=output_format,
                output_filename=output_filename,
                output_directory=output_directory,
                include_inline=include_inline,
            )
            return format_image_result(result)
        except Exception as exc:
            return _error_result(exc)

    @server.tool(
        annotations={"readOnlyHint": False, "openWorldHint": False, "idempotentHint": False},
        structured_output=False,
    )
    async def edit_image(
        prompt: Annotated[str, Field(description="Alterações desejadas e partes a preservar")],
        image_paths: Annotated[
            list[str], Field(description="De uma a quatro imagens PNG/JPEG/WebP locais")
        ],
        mask_path: Annotated[
            str | None, Field(description="Máscara PNG/JPEG/WebP local opcional")
        ] = None,
        size: str = "auto",
        quality: Quality = "medium",
        background: Background = "auto",
        output_format: OutputFormat = "png",
        output_filename: str | None = None,
        output_directory: str | None = None,
        include_inline: bool = True,
    ) -> CallToolResult:
        """Edita imagens locais com $imagegen, preservando o que o prompt não mandar alterar."""
        try:
            result = await active_service.edit_image(
                prompt=prompt,
                image_paths=image_paths,
                mask_path=mask_path,
                size=size,
                quality=quality,
                background=background,
                output_format=output_format,
                output_filename=output_filename,
                output_directory=output_directory,
                include_inline=include_inline,
            )
            return format_image_result(result)
        except Exception as exc:
            return _error_result(exc)

    @server.tool(
        annotations={"readOnlyHint": True, "openWorldHint": False},
        structured_output=False,
    )
    async def imagegen_status(run_non_consuming_probe: bool = False) -> CallToolResult:
        """Mostra backend, limites e saída; o probe opcional não gera imagem."""
        try:
            status = await active_service.imagegen_status(
                run_non_consuming_probe=run_non_consuming_probe
            )
            structured = status.model_dump(mode="json")
            return CallToolResult(
                content=[TextContent(text=json.dumps(structured, ensure_ascii=False, indent=2))],
                structuredContent=structured,
            )
        except Exception as exc:
            return _error_result(exc)

    return server


def run_server(settings: Settings | None = None) -> None:
    create_mcp_server(settings).run(transport="stdio")
