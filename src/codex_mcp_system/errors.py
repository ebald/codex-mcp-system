from __future__ import annotations


class CodexMCPError(Exception):
    """Erro público e acionável do servidor."""


class ConfigurationError(CodexMCPError):
    pass


class CodexNotFoundError(CodexMCPError):
    pass


class AppServerStartError(CodexMCPError):
    pass


class AppServerProtocolError(CodexMCPError):
    pass


class AuthenticationRequiredError(CodexMCPError):
    pass


class APIKeyAuthenticationBlockedError(CodexMCPError):
    pass


class ImagegenUnavailableError(CodexMCPError):
    pass


class UsageLimitError(CodexMCPError):
    pass


class PolicyRefusalError(CodexMCPError):
    pass


class GenerationTimeoutError(CodexMCPError):
    pass


class TurnFailedError(CodexMCPError):
    pass


class ArtifactNotFoundError(CodexMCPError):
    pass


class InvalidImageError(CodexMCPError):
    pass


class InvalidPathError(CodexMCPError):
    pass


class OutputDirectoryError(CodexMCPError):
    pass
