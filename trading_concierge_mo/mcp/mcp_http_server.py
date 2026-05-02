from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from mcp_server import (
    call_tool,
    get_prompt,
    list_prompts,
    list_resources,
    list_tools,
    read_resource,
)


app = FastAPI(
    title="Trade Blotter MCP HTTP Bridge",
    description="HTTP bridge for MCP tools/resources/prompts",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ToolCallRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class PromptRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


def _to_dict(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return obj


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/tools")
async def http_list_tools() -> list[dict[str, Any]]:
    tools = await list_tools()
    return [_to_dict(tool) for tool in tools]


@app.get("/resources")
async def http_list_resources() -> list[dict[str, Any]]:
    resources = await list_resources()
    return [_to_dict(resource) for resource in resources]


@app.get("/prompts")
async def http_list_prompts() -> list[dict[str, Any]]:
    prompts = await list_prompts()
    return [_to_dict(prompt) for prompt in prompts]


@app.get("/resource")
async def http_read_resource(uri: str) -> dict[str, Any]:
    try:
        content = await read_resource(uri)
        return {"uri": uri, "content": content}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tool/{name}")
async def http_call_tool(name: str, payload: ToolCallRequest) -> dict[str, Any]:
    try:
        result = await call_tool(name, payload.arguments)
        return {"name": name, "content": [_to_dict(item) for item in result]}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/prompt/{name}")
async def http_get_prompt(name: str, payload: PromptRequest) -> dict[str, Any]:
    try:
        result = await get_prompt(name, payload.arguments)
        result_dict = _to_dict(result)
        try:
            api_docs = await read_resource("resource://trade-blotter/api-docs")
        except Exception:
            api_docs = ""
        if api_docs:
            docs_message = {
                "role": "system",
                "content": {"type": "text", "text": api_docs},
            }
            messages = result_dict.get("messages")
            if isinstance(messages, list):
                result_dict["messages"] = [docs_message, *messages]
            else:
                result_dict["messages"] = [docs_message]
        return result_dict
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

