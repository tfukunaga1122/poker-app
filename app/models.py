from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Literal


ImportStatus = Literal[
    "recorded",
    "awaiting_score_input",
    "manual_recorded",
    "duplicate",
    "unknown_group",
    "unknown_user",
    "ocr_failed",
    "invalid_image",
]


@dataclass(frozen=True)
class GroupConfig:
    group_id: str
    group_name: str
    league: str
    rate_divisor: int
    active: bool


@dataclass(frozen=True)
class UserMapping:
    line_user_id: str
    line_display_name: str
    player_name: str
    league: str
    active: bool


@dataclass(frozen=True)
class OCRResult:
    room_id: str
    raw_score: int
    source_text: str


@dataclass(frozen=True)
class PendingScoreInput:
    """収支だけを手入力で補完するため、一時的に保持する画像の情報。"""

    message_id: str
    group_id: str
    line_user_id: str
    player_name: str
    league: str
    room_id: str
    received_at: str


@dataclass(frozen=True)
class ImportRecord:
    message_id: str
    group_id: str
    group_name: str
    line_user_id: str
    line_display_name: str
    player_name: str
    league: str
    room_id: str
    raw_score: int | None
    converted_score: int | None
    status: ImportStatus
    detail: str
    received_at: str

    def to_row(self) -> list[str | int]:
        return [
            self.message_id,
            self.group_id,
            self.group_name,
            self.line_user_id,
            self.line_display_name,
            self.player_name,
            self.league,
            self.room_id,
            "" if self.raw_score is None else self.raw_score,
            "" if self.converted_score is None else self.converted_score,
            self.status,
            self.detail,
            self.received_at,
        ]


def convert_score(raw_score: int, rate_divisor: int) -> int:
    """既存アプリと同じく、倍率適用後に10単位でゼロ方向へ切り捨てる。"""
    if rate_divisor <= 0:
        raise ValueError("換算率は1以上にしてください。")

    sign = 1 if raw_score >= 0 else -1
    points = Decimal(abs(raw_score)) / Decimal(rate_divisor) / Decimal(10)
    return int(points.quantize(Decimal("1"), rounding=ROUND_DOWN) * 10) * sign
