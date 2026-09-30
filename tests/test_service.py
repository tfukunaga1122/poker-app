import asyncio

from app.models import GroupConfig, OCRResult, PendingScoreInput, UserMapping
from app.ocr import NotResultScreenError, ScoreReadError
from app.service import ResultImportService


class FakeLine:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def get_group_member_profile(self, group_id: str, user_id: str) -> dict[str, str]:
        return {"displayName": f"LINE-{user_id}"}

    async def get_message_content(self, message_id: str) -> bytes:
        return b"image"

    async def reply_text(self, reply_token: str, text: str) -> None:
        self.replies.append(text)


class FakeSheets:
    def __init__(self) -> None:
        self.imports = []
        self.scores = []
        self.pending: dict[str, PendingScoreInput] = {}

    def has_message(self, message_id: str) -> bool:
        return any(record.message_id == message_id for record in self.imports)

    def find_group(self, group_id: str) -> GroupConfig:
        return GroupConfig(group_id, "記録グループ", "漢気リーグ", 30, True)

    def find_user(self, user_id: str, league: str) -> UserMapping:
        return UserMapping(user_id, "", {"U1": "たくみ", "U2": "りょうや"}[user_id], league, True)

    def league_exists(self, league: str) -> bool:
        return league == "漢気リーグ"

    def find_player_name(self, league: str, requested_name: str) -> str | None:
        return {"タクミツ": "たくみつ", "たくみつ": "たくみつ"}.get(requested_name)

    def upsert_group(self, group: GroupConfig) -> None:
        self.group = group

    def upsert_user(self, mapping: UserMapping) -> None:
        self.mapping = mapping

    def append_score(self, player_name: str, score: int, league: str, recorded_at: str) -> None:
        self.scores.append((player_name, score, league, recorded_at))

    def append_import(self, record) -> None:
        self.imports.append(record)

    def append_pending_score_input(self, pending: PendingScoreInput) -> None:
        self.pending[pending.message_id] = pending

    def find_pending_score_input(self, group_id: str, user_id: str, room_id: str | None = None):
        matches = [
            pending for pending in self.pending.values()
            if pending.group_id == group_id and pending.line_user_id == user_id
            and (room_id is None or pending.room_id == room_id)
        ]
        return matches[0] if len(matches) == 1 else None

    def resolve_pending_score_input(self, message_id: str) -> None:
        self.pending.pop(message_id, None)

    def room_total(self, group_id: str, room_id: str) -> int:
        return sum(record.converted_score or 0 for record in self.imports if record.room_id == room_id)

    def league_month_total(self, league: str, year_month: str) -> int:
        return sum(record.converted_score or 0 for record in self.imports)


def test_service_records_score_and_reports_month_total(monkeypatch) -> None:
    line = FakeLine()
    sheets = FakeSheets()
    service = ResultImportService(line, sheets)

    monkeypatch.setattr("app.service.read_result_image", lambda _: OCRResult("916809", 62500, ""))
    asyncio.run(service.process_image_event({
        "source": {"groupId": "G1", "userId": "U1"},
        "message": {"id": "M1"},
        "replyToken": "token",
    }))

    assert sheets.scores[0][0:3] == ("たくみ", 2080, "漢気リーグ")
    assert "合計ポイントは +2,080pt" in line.replies[-1]


def test_service_reports_zero_when_month_becomes_balanced(monkeypatch) -> None:
    line = FakeLine()
    sheets = FakeSheets()
    service = ResultImportService(line, sheets)
    scores = iter([62500, -62500])
    monkeypatch.setattr(
        "app.service.read_result_image",
        lambda _: OCRResult("916809", next(scores), ""),
    )

    for user_id, message_id in (("U1", "M1"), ("U2", "M2")):
        asyncio.run(service.process_image_event({
            "source": {"groupId": "G1", "userId": user_id},
            "message": {"id": message_id},
            "replyToken": "token",
        }))

    assert "合計ポイントは 0" in line.replies[-1]


def test_service_registers_existing_player_from_katakana_name() -> None:
    line = FakeLine()
    sheets = FakeSheets()
    service = ResultImportService(line, sheets)

    asyncio.run(service.process_text_event({
        "source": {"groupId": "G1", "userId": "U1"},
        "message": {"type": "text", "text": "登録タクミツ"},
        "replyToken": "token",
    }))

    assert sheets.mapping.player_name == "たくみつ"
    assert "登録しました" in line.replies[-1]


def test_service_silently_ignores_unrelated_image(monkeypatch) -> None:
    line = FakeLine()
    sheets = FakeSheets()
    service = ResultImportService(line, sheets)

    monkeypatch.setattr(
        "app.service.read_result_image",
        lambda _: (_ for _ in ()).throw(NotResultScreenError("結果画面ではありません。")),
    )
    asyncio.run(service.process_image_event({
        "source": {"groupId": "G1", "userId": "U1"},
        "message": {"id": "M1"},
        "replyToken": "token",
    }))

    assert line.replies == []
    assert sheets.imports == []
    assert sheets.scores == []


def test_service_accepts_line_score_when_only_score_ocr_failed(monkeypatch) -> None:
    line = FakeLine()
    sheets = FakeSheets()
    service = ResultImportService(line, sheets)
    monkeypatch.setattr(
        "app.service.read_result_image",
        lambda _: (_ for _ in ()).throw(ScoreReadError("532168")),
    )

    asyncio.run(service.process_image_event({
        "source": {"groupId": "G1", "userId": "U1"},
        "message": {"id": "M1"},
        "replyToken": "token",
    }))
    assert "入力 -4400" in line.replies[-1]

    asyncio.run(service.process_text_event({
        "source": {"groupId": "G1", "userId": "U1"},
        "message": {"type": "text", "id": "M2", "text": "入力 -4400"},
        "replyToken": "token",
    }))

    assert sheets.scores[-1][0:3] == ("たくみ", -140, "漢気リーグ")
    assert "手入力で記録しました" in line.replies[-1]


def test_service_records_named_player_without_result_image() -> None:
    line = FakeLine()
    sheets = FakeSheets()
    service = ResultImportService(line, sheets)

    asyncio.run(service.process_text_event({
        "source": {"groupId": "G1", "userId": "U1"},
        "message": {"type": "text", "id": "M3", "text": "手動入力 タクミツ -4400"},
        "replyToken": "token",
    }))

    assert sheets.scores[-1][0:3] == ("たくみつ", -140, "漢気リーグ")
    assert "合計ポイントは -140pt" in line.replies[-1]
