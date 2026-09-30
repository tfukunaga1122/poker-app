from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any
import unicodedata

from googleapiclient.discovery import build
from zoneinfo import ZoneInfo

from .models import GroupConfig, ImportRecord, PendingScoreInput, UserMapping


SCORES_HEADERS = ["名前", "スコア", "リーグ", "日付"]
LINE_USERS_HEADERS = ["line_user_id", "LINE表示名", "名前", "リーグ", "有効", "登録日時"]
LINE_GROUPS_HEADERS = ["group_id", "グループ名", "リーグ", "換算率", "有効", "登録日時"]
OCR_IMPORTS_HEADERS = [
    "line_message_id",
    "group_id",
    "グループ名",
    "line_user_id",
    "LINE表示名",
    "名前",
    "リーグ",
    "部屋ID",
    "元収支",
    "換算後スコア",
    "状態",
    "詳細",
    "受信日時",
]
PENDING_SCORE_INPUT_HEADERS = [
    "line_message_id",
    "group_id",
    "line_user_id",
    "名前",
    "リーグ",
    "部屋ID",
    "状態",
    "受信日時",
    "解決日時",
]
SCHEMA = {
    "line_users": LINE_USERS_HEADERS,
    "line_groups": LINE_GROUPS_HEADERS,
    "ocr_imports": OCR_IMPORTS_HEADERS,
    "pending_score_inputs": PENDING_SCORE_INPUT_HEADERS,
}


class SheetsRepository:
    def __init__(self, spreadsheet_id: str) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.service = build("sheets", "v4", cache_discovery=False)

    def _values(self) -> Any:
        return self.service.spreadsheets().values()

    def _read_rows(self, sheet_name: str) -> list[dict[str, str]]:
        response = self._values().get(
            spreadsheetId=self.spreadsheet_id, range=f"{sheet_name}!A:Z"
        ).execute()
        values: list[list[str]] = response.get("values", [])
        if len(values) < 2:
            return []
        headers = values[0]
        return [
            {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
            for row in values[1:]
        ]

    def append(self, sheet_name: str, row: Iterable[str | int]) -> None:
        self._values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{sheet_name}!A:Z",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [list(row)]},
        ).execute()

    def _upsert(self, sheet_name: str, key_columns: dict[str, str], row: list[str | int]) -> None:
        """キーが一致する行を更新し、存在しなければ末尾へ追加する。"""
        response = self._values().get(
            spreadsheetId=self.spreadsheet_id, range=f"{sheet_name}!A:Z"
        ).execute()
        values: list[list[str]] = response.get("values", [])
        if values:
            headers = values[0]
            for row_number, current in enumerate(values[1:], start=2):
                record = {
                    header: current[index] if index < len(current) else ""
                    for index, header in enumerate(headers)
                }
                if all(record.get(column, "") == value for column, value in key_columns.items()):
                    last_column = chr(ord("A") + len(row) - 1)
                    self._values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f"{sheet_name}!A{row_number}:{last_column}{row_number}",
                        valueInputOption="USER_ENTERED",
                        body={"values": [row]},
                    ).execute()
                    return
        self.append(sheet_name, row)

    def find_group(self, group_id: str) -> GroupConfig | None:
        for row in self._read_rows("line_groups"):
            if row.get("group_id") == group_id and row.get("有効", "").upper() != "FALSE":
                try:
                    divisor = int(row.get("換算率") or 1)
                except ValueError:
                    continue
                return GroupConfig(
                    group_id=group_id,
                    group_name=row.get("グループ名", ""),
                    league=row.get("リーグ", ""),
                    rate_divisor=divisor,
                    active=True,
                )
        return None

    def find_user(self, line_user_id: str, league: str) -> UserMapping | None:
        for row in self._read_rows("line_users"):
            if (
                row.get("line_user_id") == line_user_id
                and row.get("リーグ") == league
                and row.get("有効", "").upper() != "FALSE"
            ):
                return UserMapping(
                    line_user_id=line_user_id,
                    line_display_name=row.get("LINE表示名", ""),
                    player_name=row.get("名前", ""),
                    league=league,
                    active=True,
                )
        return None

    def league_exists(self, league: str) -> bool:
        return any(row.get("リーグ名", "") == league for row in self._read_rows("leagues"))

    def find_player_name(self, league: str, requested_name: str) -> str | None:
        normalized_requested = _normalize_name(requested_name)
        for row in self._read_rows("players"):
            player_name = row.get("名前", "")
            if row.get("リーグ") == league and _normalize_name(player_name) == normalized_requested:
                return player_name
        return None

    def upsert_group(self, group: GroupConfig) -> None:
        self._upsert(
            "line_groups",
            {"group_id": group.group_id},
            [
                group.group_id,
                group.group_name,
                group.league,
                group.rate_divisor,
                "TRUE" if group.active else "FALSE",
                jst_timestamp(),
            ],
        )

    def upsert_user(self, mapping: UserMapping) -> None:
        self._upsert(
            "line_users",
            {"line_user_id": mapping.line_user_id, "リーグ": mapping.league},
            [
                mapping.line_user_id,
                mapping.line_display_name,
                mapping.player_name,
                mapping.league,
                "TRUE" if mapping.active else "FALSE",
                jst_timestamp(),
            ],
        )

    def has_message(self, message_id: str) -> bool:
        return any(row.get("line_message_id") == message_id for row in self._read_rows("ocr_imports"))

    def append_import(self, record: ImportRecord) -> None:
        self.append("ocr_imports", record.to_row())

    def append_pending_score_input(self, pending: PendingScoreInput) -> None:
        self._upsert(
            "pending_score_inputs",
            {"line_message_id": pending.message_id},
            [
                pending.message_id,
                pending.group_id,
                pending.line_user_id,
                pending.player_name,
                pending.league,
                pending.room_id,
                "pending",
                pending.received_at,
                "",
            ],
        )

    def find_pending_score_input(
        self, group_id: str, line_user_id: str, room_id: str | None = None
    ) -> PendingScoreInput | None:
        matches: list[dict[str, str]] = []
        for row in self._read_rows("pending_score_inputs"):
            if (
                row.get("group_id") == group_id
                and row.get("line_user_id") == line_user_id
                and row.get("状態") == "pending"
                and (room_id is None or row.get("部屋ID") == room_id)
            ):
                matches.append(row)
        if not matches:
            return None
        # 部屋IDなしの入力は、公式LINEが最後に案内した（最も新しい）画像へ補完する。
        row = max(matches, key=lambda item: item.get("受信日時", ""))
        return PendingScoreInput(
            message_id=row.get("line_message_id", ""),
            group_id=row.get("group_id", ""),
            line_user_id=row.get("line_user_id", ""),
            player_name=row.get("名前", ""),
            league=row.get("リーグ", ""),
            room_id=row.get("部屋ID", ""),
            received_at=row.get("受信日時", ""),
        )

    def resolve_pending_score_input(self, message_id: str) -> None:
        for row in self._read_rows("pending_score_inputs"):
            if row.get("line_message_id") != message_id:
                continue
            self._upsert(
                "pending_score_inputs",
                {"line_message_id": message_id},
                [
                    row.get("line_message_id", ""),
                    row.get("group_id", ""),
                    row.get("line_user_id", ""),
                    row.get("名前", ""),
                    row.get("リーグ", ""),
                    row.get("部屋ID", ""),
                    "recorded",
                    row.get("受信日時", ""),
                    jst_timestamp(),
                ],
            )
            return

    def append_score(self, player_name: str, score: int, league: str, recorded_at: str) -> None:
        self.append("scores", [player_name, score, league, recorded_at])

    def room_total(self, group_id: str, room_id: str) -> int:
        total = 0
        for row in self._read_rows("ocr_imports"):
            if (
                row.get("group_id") == group_id
                and row.get("部屋ID") == room_id
                and row.get("状態") in {"recorded", "manual_recorded"}
            ):
                try:
                    total += int(row.get("換算後スコア", "0"))
                except ValueError:
                    continue
        return total

    def league_month_total(self, league: str, year_month: str) -> int:
        """台帳上の同一リーグ・指定月にある全スコアの合計を返す。"""
        total = 0
        for row in self._read_rows("scores"):
            if (
                row.get("リーグ") == league
                and _is_in_year_month(row.get("日付", ""), year_month)
            ):
                try:
                    total += int(row.get("スコア", "0"))
                except ValueError:
                    continue
        return total

    def ensure_schema(self) -> list[str]:
        metadata = self.service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id, fields="sheets.properties"
        ).execute()
        existing = {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}
        missing = [(name, headers) for name, headers in SCHEMA.items() if name not in existing]
        if missing:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": name}}} for name, _ in missing]},
            ).execute()
        for name, headers in missing:
            self._values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{name}!A1",
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()
        return [name for name, _ in missing]


def jst_timestamp() -> str:
    return datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_name(value: str) -> str:
    """全半角、かな種別、空白の違いを吸収して既存選手名へ照合する。"""
    text = unicodedata.normalize("NFKC", value).strip().lower()
    text = "".join(character for character in text if not character.isspace())
    return "".join(
        chr(ord(character) - 0x60) if "ァ" <= character <= "ヶ" else character
        for character in text
    )


def _is_in_year_month(value: str, year_month: str) -> bool:
    """スプレッドシートの日付区切りの違いを吸収して月を照合する。"""
    return value.strip().replace("/", "-").startswith(year_month)
