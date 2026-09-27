from __future__ import annotations

import hashlib
import hmac
import base64
import binascii
from typing import Any

import httpx


LINE_API = "https://api.line.me/v2/bot"
LINE_DATA_API = "https://api-data.line.me/v2/bot"


class LineClient:
    def __init__(self, access_token: str, channel_secret: str) -> None:
        self.access_token = access_token
        self.channel_secret = channel_secret

    def verify_signature(self, body: bytes, signature: str | None) -> bool:
        if not signature or not self.channel_secret:
            return False
        expected = hmac.new(
            self.channel_secret.encode("utf-8"), body, hashlib.sha256
        ).digest()
        try:
            actual = base64.b64decode(signature, validate=True)
        except (ValueError, binascii.Error):
            return False
        return hmac.compare_digest(expected, actual)

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def get_message_content(self, message_id: str) -> bytes:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{LINE_DATA_API}/message/{message_id}/content", headers=self._headers
            )
            response.raise_for_status()
            return response.content

    async def get_group_member_profile(self, group_id: str, user_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{LINE_API}/group/{group_id}/member/{user_id}", headers=self._headers
            )
            response.raise_for_status()
            return response.json()

    async def reply_text(self, reply_token: str, text: str) -> None:
        if not reply_token:
            return
        payload = {"replyToken": reply_token, "messages": [{"type": "text", "text": text}]}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{LINE_API}/message/reply", headers=self._headers, json=payload
            )
            response.raise_for_status()
