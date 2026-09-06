from __future__ import annotations

from pathlib import Path

import pytest

from codex_mcp_system.config import DEFAULT_INLINE_IMAGE_MAX_BYTES, Settings
from codex_mcp_system.errors import ConfigurationError


def test_settings_from_environment(tmp_path: Path) -> None:
    settings = Settings.from_env(
        {
            "CODEX_MCP_OUTPUT_DIR": str(tmp_path),
            "CODEX_MCP_TIMEOUT_SECONDS": "42",
            "CODEX_MCP_INLINE_IMAGE_MAX_BYTES": "1234",
            "CODEX_MCP_LOG_LEVEL": "debug",
            "CODEX_MCP_ALLOW_API_KEY": "false",
        }
    )
    assert settings.output_dir == tmp_path
    assert settings.timeout_seconds == 42
    assert settings.inline_image_max_bytes == 1234
    assert settings.log_level == "DEBUG"
    assert settings.allow_api_key is False


def test_defaults_are_conservative() -> None:
    settings = Settings.from_env({})
    assert settings.timeout_seconds == 600
    assert settings.inline_image_max_bytes == DEFAULT_INLINE_IMAGE_MAX_BYTES
    assert settings.allow_api_key is False
    assert settings.output_dir.name == __import__("datetime").date.today().isoformat()


def test_child_environment_removes_only_openai_key() -> None:
    source = {"OPENAI_API_KEY": "secret", "PATH": "/bin", "KEEP_ME": "yes"}
    child = Settings(output_dir=Path("/tmp")).child_environment(source)
    assert "OPENAI_API_KEY" not in child
    assert child["KEEP_ME"] == "yes"
    assert source["OPENAI_API_KEY"] == "secret"


@pytest.mark.parametrize("value", ["maybe", "", "2"])
def test_invalid_boolean_is_rejected(value: str) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_env({"CODEX_MCP_ALLOW_API_KEY": value})


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "0", "-1"])
def test_non_finite_or_non_positive_timeout_is_rejected(value: str) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_env({"CODEX_MCP_TIMEOUT_SECONDS": value})
