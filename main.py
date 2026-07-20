from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import run_map_agent
from .agent_llm import run_chat_agent
from .config import get_settings
from .services.auth import verify_api_key
from .tools.feishu_tool import FeishuClient

settings = get_settings()
app = FastAPI(title="Feishu Map Agent", version="0.1.0")

Path(settings.map_output_dir).mkdir(parents=True, exist_ok=True)
app.mount("/maps", StaticFiles(directory=settings.map_output_dir, html=True), name="maps")


@app.get("/chat", response_class=HTMLResponse)
def chat_page():
    chat_html = Path(__file__).parent / "static" / "chat.html"
    return chat_html.read_text(encoding="utf-8")


class ManualRunRequest(BaseModel):
    app_token: str
    table_id: str


class ChatRequest(BaseModel):
    query: str = Field(..., max_length=4096, description="用户自然语言查询")
    session_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/agent/run")
def manual_run(
    request: ManualRunRequest,
    _auth: None = Depends(verify_api_key),
):
    result = run_map_agent(app_token=request.app_token, table_id=request.table_id)
    if result.error:
        raise HTTPException(status_code=500, detail=result.error)

    return {
        "task_id": result.task_id,
        "success_count": result.success_count,
        "url": f"{settings.public_base_url.rstrip('/')}/maps/{result.task_id}.html",
        "logs": result.logs,
    }


@app.post("/agent/chat")
def agent_chat(
    request: ChatRequest,
    _auth: None = Depends(verify_api_key),
):
    result = run_chat_agent(request.query, request.session_id)
    return result


@app.get("/agent/run/openapi.json")
def openapi_spec(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "openapi": "3.0.1",
        "info": {
            "title": "Map Agent",
            "description": "Generate interactive maps from Feishu Bitable data. Provide an app_token and table_id to create a map with geocoded locations.",
            "version": "1.0.0",
        },
        "servers": [{"url": base_url}],
        "paths": {
            "/agent/run": {
                "post": {
                    "operationId": "generate_map",
                    "summary": "Generate an interactive map from a Feishu Bitable",
                    "description": "Reads location data from the specified Feishu Bitable table, geocodes addresses via AMap, and renders an interactive HTML map.",
                    "security": [{"ApiKeyAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["app_token", "table_id"],
                                    "properties": {
                                        "app_token": {
                                            "type": "string",
                                            "description": "The Feishu Bitable app token (found in the Bitable URL)",
                                        },
                                        "table_id": {
                                            "type": "string",
                                            "description": "The Feishu Bitable table ID (found in the Bitable URL)",
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Map generated successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "task_id": {"type": "string"},
                                            "success_count": {"type": "integer"},
                                            "url": {"type": "string", "description": "URL to the generated map HTML"},
                                            "logs": {"type": "array", "items": {"type": "string"}},
                                        },
                                    }
                                }
                            },
                        },
                    },
                }
            }
        },
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Bearer token authentication. Set via API_KEY in .env",
                }
            }
        },
    }
