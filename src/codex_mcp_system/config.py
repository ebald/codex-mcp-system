from __future__ import annotations

import math
import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from codex_mcp_system.errors import CodexNotFoundError, ConfigurationError

DEFAULT_TIMEOUT_SECONDS = 600.0
DEFAULT_INLINE_IMAGE_MAX_BYTES = 2 * 1024 * 1024
MAX_JSONL_BYTES = 64 * 1024 * 1024


def _parse_bool(name: str, raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} deve ser true ou false")


def _parse_positive_float(name: str, raw: str | None, *, default: float) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} deve ser um número") from exc
    if not math.isfinite(value) or value <= 0:
        raise ConfigurationError(f"{name} deve ser um número finito maior que zero")
    return value


def _parse_positive_int(name: str, raw: str | None, *, default: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} deve ser um inteiro") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} deve ser maior que zero")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    output_dir: Path
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    codex_bin: str = "codex"
    log_level: str = "INFO"
    inline_image_max_bytes: int = DEFAULT_INLINE_IMAGE_MAX_BYTES
    allow_api_key: bool = False
    jsonl_max_bytes: int = MAX_JSONL_BYTES

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if environ is None else environ
        raw_output = env.get("CODEX_MCP_OUTPUT_DIR")
        if raw_output:
            output_dir = Path(raw_output).expanduser()
        else:
            output_dir = Path.home() / "Pictures" / "codex-mcp-system" / date.today().isoformat()
        log_level = env.get("CODEX_MCP_LOG_LEVEL", "INFO").strip().upper()
        if log_level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ConfigurationError("CODEX_MCP_LOG_LEVEL inválido")
        return cls(
            output_dir=output_dir,
            timeout_seconds=_parse_positive_float(
                "CODEX_MCP_TIMEOUT_SECONDS",
                env.get("CODEX_MCP_TIMEOUT_SECONDS"),
                default=DEFAULT_TIMEOUT_SECONDS,
            ),
            codex_bin=env.get("CODEX_MCP_CODEX_BIN", "codex").strip() or "codex",
            log_level=log_level,
            inline_image_max_bytes=_parse_positive_int(
                "CODEX_MCP_INLINE_IMAGE_MAX_BYTES",
                env.get("CODEX_MCP_INLINE_IMAGE_MAX_BYTES"),
                default=DEFAULT_INLINE_IMAGE_MAX_BYTES,
            ),
            allow_api_key=_parse_bool(
                "CODEX_MCP_ALLOW_API_KEY",
                env.get("CODEX_MCP_ALLOW_API_KEY"),
                default=False,
            ),
        )

    def resolve_codex_bin(self) -> str:
        candidate = Path(self.codex_bin).expanduser()
        if candidate.is_absolute() or candidate.parent != Path("."):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate.resolve())
            raise CodexNotFoundError(f"Executável Codex não encontrado: {candidate}")
        resolved = shutil.which(self.codex_bin)
        if resolved is None:
            raise CodexNotFoundError(
                "Executável 'codex' não encontrado. Instale/abra o Codex e configure "
                "CODEX_MCP_CODEX_BIN se necessário."
            )
        return resolved

    def child_environment(self, environ: Mapping[str, str] | None = None) -> dict[str, str]:
        child = dict(os.environ if environ is None else environ)
        child.pop("OPENAI_API_KEY", None)
        return child
