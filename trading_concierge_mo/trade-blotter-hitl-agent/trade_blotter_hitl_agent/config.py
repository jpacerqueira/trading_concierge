"""Environment-driven configuration for the Trade Blotter HITL agent."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from `.env` / process environment.

    Attributes are documented inline; see `.env.example` for the canonical list.
    """

    # --- MCP HTTP bridge ---
    mcp_bridge_url: str = Field(
        default="http://localhost:8080",
        validation_alias="MCP_BRIDGE_URL",
        description="Base URL of mcp_http_server.py.",
    )
    mcp_bridge_timeout: float = Field(
        default=30.0,
        validation_alias="MCP_BRIDGE_TIMEOUT",
        description="HTTP timeout for bridge calls, in seconds.",
    )
    mcp_bridge_token: Optional[str] = Field(
        default=None,
        validation_alias="MCP_BRIDGE_TOKEN",
        description="Optional bearer token if the bridge is auth-protected.",
    )

    # --- Model ---
    adk_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias="ADK_MODEL",
        description="Gemini model name used by the agent.",
    )

    # --- HITL ---
    tool_classification_path: str = Field(
        default="assets/tool_classification.yaml",
        validation_alias="TOOL_CLASSIFICATION_PATH",
        description="Path (relative to the package root or absolute) to the YAML "
        "that classifies MCP tools as read_only / mutating.",
    )
    hitl_fail_closed: bool = Field(
        default=True,
        validation_alias="HITL_FAIL_CLOSED",
        description="If True, MCP tools that don't match any classification rule "
        "are treated as mutating (require approval).",
    )
    hitl_skills_max_chars: int = Field(
        default=120_000,
        validation_alias="HITL_SKILLS_MAX_CHARS",
        description="Max length of the compiled skills digest in the system prompt; "
        "0 means unlimited.",
    )
    hitl_write_skills_snapshot: bool = Field(
        default=False,
        validation_alias="HITL_WRITE_SKILLS_SNAPSHOT",
        description="If True, write compiled skills markdown to hitl_skills_snapshot_path.",
    )
    hitl_skills_snapshot_path: str = Field(
        default="assets/cache/compiled_skills.md",
        validation_alias="HITL_SKILLS_SNAPSHOT_PATH",
        description="Path (package-relative or absolute) for optional skills snapshot.",
    )

    # --- Direct Trade API (same REST surface MCP uses; authorized for HITL) ---
    trade_api_base_url: str = Field(
        default="http://trade-api:8000",
        validation_alias="TRADE_API_BASE_URL",
        description="Base URL of the Trade Blotter REST API (parallel to MCP tools).",
    )
    trade_api_timeout: float = Field(
        default=30.0,
        validation_alias="TRADE_API_TIMEOUT",
        description="HTTP timeout for Trade API calls.",
    )
    trade_api_bearer_token: Optional[str] = Field(
        default=None,
        validation_alias="TRADE_API_BEARER_TOKEN",
        description="Static Bearer token for Trade API (optional; overrides OAuth when set).",
    )
    trade_api_direct_tools_enabled: bool = Field(
        default=True,
        validation_alias="TRADE_API_DIRECT_TOOLS",
        description="Expose trade_api_* ADK tools that call TRADE_API_BASE_URL directly.",
    )
    use_mock_api: bool = Field(
        default=False,
        validation_alias="USE_MOCK_API",
        description="If True, skip Murex OAuth for Trade API (local/mock).",
    )
    mx_username: Optional[str] = Field(default=None, validation_alias="MX_USERNAME")
    mx_password: Optional[str] = Field(default=None, validation_alias="MX_PASSWORD")
    mx_group: Optional[str] = Field(default=None, validation_alias="MX_GROUP")
    mx_fo_desk: Optional[str] = Field(default=None, validation_alias="MX_FO_DESK")
    mx_load_balancer_url: Optional[str] = Field(
        default=None,
        validation_alias="MX_LOAD_BALANCER_URL",
        description="Murex LB URL for OAuth (same as mcp-server token flow).",
    )
    mx_verify_ssl: bool = Field(
        default=False,
        validation_alias="MX_VERIFY_SSL",
        description="Verify TLS when calling Murex OAuth / Trade API.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def resolve_classification_path(self, package_root: Path) -> Path:
        """Resolve the classification YAML path against the package root."""
        candidate = Path(self.tool_classification_path)
        if candidate.is_absolute():
            return candidate
        return (package_root / candidate).resolve()

    def resolve_skills_snapshot_path(self, package_root: Path) -> Path:
        candidate = Path(self.hitl_skills_snapshot_path)
        if candidate.is_absolute():
            return candidate
        return (package_root / candidate).resolve()


settings = Settings()
