"""HTTP A2A (agent-to-agent) bridge for the desktop app and peer services.

Runs alongside `adk web` on a separate port. Offers tool classification
(aligned with ``tool_classification.yaml``), task planning, and step
validation using the same Gemini key as the ADK agent.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .hitl import load_classification
from .mcp_client import MCPHTTPClient

logger = logging.getLogger(__name__)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _gemini_generate(prompt: str, *, model: str | None = None, temperature: float = 0.2) -> str:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY / GEMINI_API_KEY not set")
    m = model or settings.adk_model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, json=payload)
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=resp.json().get("error", {}).get("message", resp.text),
            )
        data = resp.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


def _classification():
    return load_classification(
        settings.resolve_classification_path(PACKAGE_ROOT),
        fail_closed=settings.hitl_fail_closed,
    )


app = FastAPI(title="Trade Blotter HITL A2A", version="1.0.0")

_cors = os.environ.get("A2A_CORS_ORIGINS", "*")
_origins = [o.strip() for o in _cors.split(",") if o.strip()] if _cors != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ClassifyBody(BaseModel):
    names: list[str] = Field(..., min_length=1)


class PlanBody(BaseModel):
    goal: str = Field(..., min_length=1)
    context: str | None = None
    tool_names: list[str] | None = None


class ValidateStepBody(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None
    prior_steps: list[str] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "hitl-a2a"}


@app.get("/v1/a2a/health")
def a2a_health() -> dict[str, Any]:
    out: dict[str, Any] = {"a2a": "ok", "mcp_bridge": None}
    try:
        with MCPHTTPClient(
            settings.mcp_bridge_url,
            timeout=min(settings.mcp_bridge_timeout, 10.0),
            token=settings.mcp_bridge_token,
        ) as c:
            out["mcp_bridge"] = c.health()
    except Exception as exc:  # noqa: BLE001
        out["mcp_bridge"] = {"status": "error", "error": str(exc)}
    return out


@app.post("/v1/a2a/classify")
def classify_tools(body: ClassifyBody) -> dict[str, Any]:
    cls = _classification()
    return {
        "fail_closed": cls.fail_closed,
        "tools": [
            {"name": n, "kind": cls.classify(n)}
            for n in body.names
        ],
    }


@app.post("/v1/a2a/plan")
def plan_task(body: PlanBody) -> dict[str, Any]:
    names = body.tool_names
    if not names:
        try:
            with MCPHTTPClient(
                settings.mcp_bridge_url,
                timeout=settings.mcp_bridge_timeout,
                token=settings.mcp_bridge_token,
            ) as c:
                names = [t.name for t in c.list_tools()]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not list MCP tools for planning: %s", exc)
            names = []

    cls = _classification()
    ro = [n for n in names if cls.classify(n) == "read_only"]
    mut = [n for n in names if cls.classify(n) == "mutating"]

    prompt = f"""You are the planning component of a Trade Blotter Human-in-the-Loop agent.
Decompose the user's goal into ordered steps for an assistant that may only call MCP tools.

Rules:
- Prefer read-only tools first to gather context: {ro or "(discover via list_tools)"}.
- Any step that uses a mutating tool MUST be explicitly marked "requires_human_approval": true.
Mutating tools on this bridge: {mut or "(none discovered; still flag place/cancel/amend patterns)"}.

Goal: {body.goal}
Extra context: {body.context or "(none)"}

Respond with ONLY valid JSON (no markdown):
{{
  "summary": "one line",
  "steps": [
    {{
      "order": 1,
      "description": "what this step does",
      "suggested_tool": "tool_name or null",
      "arguments_hint": {{}},
      "requires_human_approval": false,
      "risk_notes": "optional"
    }}
  ],
  "open_questions": ["optional strings"]
}}
"""
    raw = _gemini_generate(prompt, temperature=0.15)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            parsed = json.loads(raw[start : end + 1])
        else:
            raise HTTPException(status_code=502, detail="Planner did not return JSON") from None
    return {"plan": parsed, "tools": {"read_only": ro, "mutating": mut}}


@app.post("/v1/a2a/validate_step")
def validate_step(body: ValidateStepBody) -> dict[str, Any]:
    cls = _classification()
    kind = cls.classify(body.tool)
    prior = "\n".join(body.prior_steps or []) or "(none)"
    prompt = f"""You validate a single MCP tool call for a trade blotter assistant.

Tool: {body.tool}
Classification: {kind} (read_only tools may run without approval; mutating require human sign-off)
Arguments JSON: {json.dumps(body.arguments, indent=2)}
Operator rationale: {body.rationale or "(none)"}
Prior steps summary:
{prior}

Reply with ONLY valid JSON:
{{
  "safe_to_proceed_readonly": true or false,
  "needs_human_approval": true or false,
  "issues": ["strings"],
  "suggested_fixes": ["strings"]
}}
For mutating tools, needs_human_approval must be true."""
    raw = _gemini_generate(prompt, temperature=0.1)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            parsed = json.loads(raw[start : end + 1])
        else:
            raise HTTPException(status_code=502, detail="Validator did not return JSON") from None
    return {"validation": parsed, "tool_kind": kind}


@app.get("/v1/a2a/skills")
def skills_summary() -> dict[str, str]:
    return {
        "name": "trade-blotter-hitl",
        "summary": (
            "Human-in-the-loop trade blotter agent: read-only MCP tools run immediately; "
            "mutating tools require explicit human approval and matching ticket state. "
            "Use /v1/a2a/plan for task decomposition and /v1/a2a/validate_step before execution."
        ),
    }
