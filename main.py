import logging
from pathlib import Path

# Configure logging so INFO and above messages from our app are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import run_map_agent
from agent_llm import run_chat_agent
from config import get_settings
from services.auth import verify_api_key
from tools.feishu_tool import FeishuClient
from services.feishu_webhook import handle_url_verification, extract_chat_message, is_duplicate_event
from services.feishu_reply import send_card_message, send_text_message

settings = get_settings()
from tools.db_tool import init_db
init_db(settings.db_path)
app = FastAPI(title="Feishu Map Agent", version="0.1.0")

Path(settings.map_output_dir).mkdir(parents=True, exist_ok=True)
app.mount("/maps", StaticFiles(directory=settings.map_output_dir, html=True), name="maps")


@app.get("/chat", response_class=HTMLResponse)
def chat_page():
    chat_html = Path(__file__).parent / "static" / "chat.html"
    return chat_html.read_text(encoding="utf-8")


@app.post("/feishu/webhook")
async def feishu_webhook(request: Request):
    """飞书事件回调 Webhook。

    处理飞书开放平台的 URL 验证和消息接收事件。
    消息到达后调用 ReAct Agent 处理，并通过卡片或文本回复。
    """
    logger = logging.getLogger("feishu.webhook")
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(content={}, status_code=200)

    # URL 验证（飞书首次配置时发送）
    verification = handle_url_verification(body)
    if verification:
        return verification

    # 提取消息
    msg = extract_chat_message(body)
    if not msg:
        return JSONResponse(content={}, status_code=200)

    event_id = msg.get("event_id", "")
    chat_id = msg["chat_id"]
    text = msg["text"]

    # 去重：飞书 Webhook 可能重复投递同一事件
    if is_duplicate_event(event_id):
        logger.info("跳过重复事件: event_id=%s", event_id)
        return JSONResponse(content={}, status_code=200)

    logger.info("处理飞书消息: chat_id=%s, event_id=%s", chat_id, event_id)

    # 调用 Agent（chat_id 作为 session_id 实现多轮对话）
    result = run_chat_agent(text, session_id=chat_id)

    # 回复
    map_url = result.get("map_url")
    if map_url:
        full_url = map_url if map_url.startswith("http") else f"{settings.public_base_url.rstrip('/')}/{map_url.lstrip('/')}"
        try:
            send_card_message(chat_id, "数据分布图", result.get("success_count", 0), full_url)
        except Exception:
            logger.exception("发送卡片消息失败")
            try:
                send_text_message(chat_id, f"地图已生成：{full_url}")
            except Exception:
                pass
    else:
        reply_text = result.get("reply", "抱歉，无法处理您的请求。")
        try:
            send_text_message(chat_id, reply_text)
        except Exception:
            logger.exception("发送文本消息失败")

    return JSONResponse(content={}, status_code=200)


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
