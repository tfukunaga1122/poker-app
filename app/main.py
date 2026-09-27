from __future__ import annotations

import json
import logging
import asyncio

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from .config import Settings
from .line_client import LineClient
from .service import ResultImportService
from .sheets import SheetsRepository


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings.from_env()
line_client = LineClient(settings.line_channel_access_token, settings.line_channel_secret)
app = FastAPI(title="Poker LINE Result Recorder")
# LINEからは最大8件を同時に受け付ける。一方、メモリ負荷の大きいVision OCRは
# 3件ずつ処理し、残りは同じプロセス内で待機させることで取りこぼしを防ぐ。
PROCESSING_LIMIT = asyncio.Semaphore(3)


@app.on_event("startup")
async def ensure_recorder_schema() -> None:
    """新しい手入力待ちシートを、配置後に自動で用意する。"""
    try:
        created = await asyncio.to_thread(
            SheetsRepository(settings.spreadsheet_id).ensure_schema
        )
        if created:
            logger.info("記録用シートを作成しました: %s", ", ".join(created))
    except Exception:
        # 既存の記録処理を開始不能にしない。失敗時はCloud Runログで確認できる。
        logger.exception("記録用シートの初期化に失敗しました。")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def process_event(event: dict) -> None:
    if event.get("type") != "message":
        return
    try:
        # Cloud Vision と Google Sheets は同期SDKのため、イベントループを塞がないよう
        # 個々のイベントを並行実行する。OCRはメモリ保護のため3件ずつに抑える。
        async with PROCESSING_LIMIT:
            service = ResultImportService(line_client, SheetsRepository(settings.spreadsheet_id))
            message_type = event.get("message", {}).get("type")
            message_id = event.get("message", {}).get("id", "")
            if message_type == "image":
                logger.info("画像イベントの処理を開始しました: %s", message_id)
                await service.process_image_event(event)
                logger.info("画像イベントの処理を完了しました: %s", message_id)
            elif message_type == "text":
                await service.process_text_event(event)
    except Exception:
        logger.exception("LINEイベントの処理に失敗しました: %s", event.get("message", {}).get("id", ""))


async def process_events(events: list[dict]) -> None:
    """同一Webhookにまとめて届いたイベントも並列に処理する。"""
    await asyncio.gather(*(process_event(event) for event in events))


@app.post("/callback")
async def callback(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str | None = Header(default=None),
) -> dict[str, str]:
    body = await request.body()
    if not line_client.verify_signature(body, x_line_signature):
        raise HTTPException(status_code=400, detail="LINE署名が一致しません。")
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="JSON形式が不正です。") from error

    events = payload.get("events", [])
    image_count = sum(
        event.get("type") == "message" and event.get("message", {}).get("type") == "image"
        for event in events
    )
    if image_count:
        logger.info("LINE Webhookで画像%s件を受信しました。", image_count)
    background_tasks.add_task(process_events, events)
    return {"status": "accepted"}
