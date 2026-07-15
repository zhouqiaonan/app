from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent import run_map_agent
from app.config import get_settings
from app.services.feishu_events import (
    extract_text_message,
    is_url_verification,
    verify_token,
)
from app.services.feishu_message import FeishuMessenger
from app.services.message_parser import parse_map_command
from app.tools.feishu_tool import FeishuClient

settings = get_settings()
app = FastAPI(title="Feishu Map Agent", version="0.1.0")

Path(settings.map_output_dir).mkdir(parents=True, exist_ok=True)
app.mount("/maps", StaticFiles(directory=settings.map_output_dir, html=True), name="maps")


class ManualRunRequest(BaseModel):
    app_token: str
    table_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/agent/run")
def manual_run(request: ManualRunRequest):
    result = run_map_agent(app_token=request.app_token, table_id=request.table_id)
    if result.error:
        raise HTTPException(status_code=500, detail=result.error)

    return {
        "task_id": result.task_id,
        "success_count": result.success_count,
        "url": f"{settings.public_base_url.rstrip('/')}/maps/{result.task_id}.html",
        "logs": result.logs,
    }


@app.post("/feishu/events")
async def feishu_events(request: Request):
    payload = await request.json()

    if is_url_verification(payload):
        return {"challenge": payload["challenge"]}

    try:
        verify_token(payload, settings.feishu_verification_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    chat_id, text = extract_text_message(payload)
    if "生成地图" not in text:
        return JSONResponse({"code": 0, "msg": "ignored"})

    feishu_client = FeishuClient(settings.feishu_app_id, settings.feishu_app_secret)
    messenger = FeishuMessenger(feishu_client)

    try:
        command = parse_map_command(text)
        result = run_map_agent(command.app_token, command.table_id)
        if result.error:
            reply = f"地图生成失败：{result.error}"
        else:
            url = f"{settings.public_base_url.rstrip('/')}/maps/{result.task_id}.html"
            reply = f"地图已生成：{url}\n有效地点：{result.success_count}"
    except Exception as exc:
        reply = f"地图生成失败：{exc}"

    if chat_id:
        messenger.send_text(chat_id, reply)

    return {"code": 0}
