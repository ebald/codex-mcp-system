from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from collections.abc import Sequence

from codex_mcp_system import __version__
from codex_mcp_system.config import Settings
from codex_mcp_system.errors import CodexMCPError
from codex_mcp_system.image_service import ImageService, prepare_output_directory
from codex_mcp_system.server import run_server

SMOKE_PROMPT = "A small red ceramic cube on a neutral gray background, studio lighting."


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


async def _doctor(settings: Settings) -> int:
    report: dict[str, object] = {
        "python_version": sys.version.split()[0],
        "python_supported": sys.version_info >= (3, 11),
        "api_key_present_in_parent": "OPENAI_API_KEY" in os.environ,
        "api_key_forwarded_to_app_server": False,
        "allow_api_key": settings.allow_api_key,
        "output_directory": str(settings.output_dir.expanduser().resolve()),
    }
    service = ImageService(settings)
    try:
        output_dir = prepare_output_directory(settings.output_dir)
        report["output_writable"] = True
        report["output_directory"] = str(output_dir)
        status = await service.account_status()
        report.update(status.model_dump(mode="json"))
        report["app_server_initialized"] = True
    except Exception as exc:
        report["ready"] = False
        report["error"] = (
            str(exc) if isinstance(exc, (CodexMCPError, ValueError)) else type(exc).__name__
        )
    finally:
        await service.close()
    healthy = bool(report.get("ready")) and not settings.allow_api_key
    report["doctor_ok"] = healthy
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if healthy else 1


def _login(settings: Settings) -> int:
    codex_bin = settings.resolve_codex_bin()
    result = subprocess.run(
        [codex_bin, "login"],
        env=settings.child_environment(),
        check=False,
    )
    if result.returncode != 0:
        print("O fluxo oficial 'codex login' não foi concluído.", file=sys.stderr)
        return result.returncode
    return asyncio.run(_doctor(settings))


async def _smoke_test(settings: Settings) -> int:
    service = ImageService(settings)
    try:
        result = await service.generate_image(
            prompt=SMOKE_PROMPT,
            size="1024x1024",
            quality="low",
            background="opaque",
            output_format="png",
            output_filename="smoke-test-red-ceramic-cube.png",
            include_inline=False,
        )
        payload = result.metadata.model_dump(mode="json")
        payload["warning"] = (
            "Este teste consumiu cota geral do Codex associada ao plano ChatGPT; "
            "não usou cobrança da OpenAI API."
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        message = str(exc) if isinstance(exc, (CodexMCPError, ValueError)) else type(exc).__name__
        print(f"Smoke test falhou: {message}", file=sys.stderr)
        return 1
    finally:
        await service.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-mcp-system",
        description="Servidor MCP local, pessoal e não oficial para $imagegen do Codex.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("serve", help="Inicia o servidor MCP por stdio")
    subparsers.add_parser("doctor", help="Executa diagnósticos sem gerar imagem")
    subparsers.add_parser("login", help="Executa o fluxo oficial codex login e o doctor")
    subparsers.add_parser("smoke-test", help="Gera uma única imagem low e consome cota do Codex")
    subparsers.add_parser("version", help="Exibe a versão sem iniciar o App Server")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "version":
        print(__version__)
        return
    try:
        settings = Settings.from_env()
        _configure_logging(settings.log_level)
        if args.command == "serve":
            if settings.allow_api_key:
                raise CodexMCPError("CODEX_MCP_ALLOW_API_KEY deve permanecer false.")
            run_server(settings)
            return
        if args.command == "doctor":
            raise SystemExit(asyncio.run(_doctor(settings)))
        if args.command == "login":
            raise SystemExit(_login(settings))
        if args.command == "smoke-test":
            raise SystemExit(asyncio.run(_smoke_test(settings)))
    except (CodexMCPError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
