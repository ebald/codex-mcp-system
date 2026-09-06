from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Availability = Literal[True, False, "unknown"]
Quality = Literal["low", "medium", "high"]
Background = Literal["auto", "opaque", "transparent"]
OutputFormat = Literal["png", "jpeg", "webp"]


class AccountInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    auth_mode: Literal["chatgpt", "apikey", "none", "other"]
    plan_type: str | None = None


class AccountStatus(BaseModel):
    ready: bool
    auth_mode: Literal["chatgpt", "apikey", "none", "other"]
    plan_type: str | None = None
    imagegen_available: Availability
    api_billing_blocked: bool
    codex_version: str | None = None
    message: str


class ImagegenStatus(BaseModel):
    available: Availability
    backend: str
    output_directory: str
    timeout_seconds: float
    inline_enabled: bool
    inline_max_bytes: int
    known_limitations: list[str]
    message: str


class ImageResult(BaseModel):
    message: str
    path: str
    filename: str
    mime_type: str
    width: int
    height: int
    size_bytes: int
    backend: str
    auth_mode: Literal["chatgpt"] = "chatgpt"
    quota_notice: str
    inline_included: bool


class AppServerImageArtifact(BaseModel):
    source_path: str
    status: str
    revised_prompt: str | None = None
    transparent_background: bool | None = None
