from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from codex_mcp_system.config import Settings


@pytest.fixture
def fake_codex() -> Path:
    path = Path(__file__).with_name("fake_codex.py")
    path.chmod(0o755)
    return path


@pytest.fixture
def png_file(tmp_path: Path) -> Path:
    path = tmp_path / "source.png"
    Image.new("RGBA", (32, 24), (220, 20, 30, 255)).save(path)
    return path


@pytest.fixture
def settings(tmp_path: Path, fake_codex: Path) -> Settings:
    return Settings(output_dir=tmp_path / "output", codex_bin=os.fspath(fake_codex))
