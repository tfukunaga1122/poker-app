from __future__ import annotations

import asyncio
import re
import unicodedata

from .line_client import LineClient
from .models import GroupConfig, ImportRecord, PendingScoreInput, UserMapping, convert_score
from .ocr import NotResultScreenError, OCRReadError, ScoreReadError, read_result_image
from .sheets import SheetsRepository, jst_timestamp


class ResultImportService:
    def __init__(self, line: LineClient, sheets: SheetsRepository) -> None:
        self.line = line
        self.sheets = sheets

    async def process_image_event(self, event: dict) -> None:
        source = event.get("source", {})
        message = event.get("message", {})
        group_id = source.get("groupId", "")
        user_id = source.get("userId", "")
        message_id = message.get("id", "")
        reply_token = event.get("replyToken", "")
        received_at = jst_timestamp()

        if not group_id or not user_id or not message_id:
            await self.line.reply_text(reply_token, "グループ内から送信された画像のみ記録できます。")
            return

        if await asyncio.to_thread(self.sheets.has_message, message_id):
            await self.line.reply_text(reply_token, "この画像はすでに処理済みです。")
            return

        # 画像を先に分類する。結果画面でない画像は、履歴にも残さず無反応で終える。
        ocr_error: OCRReadError | None = None
        try:
            image_bytes = await self.line.get_message_content(message_id)
            result = await asyncio.to_thread(read_result_image, image_bytes)
        except NotResultScreenError:
            return
        except OCRReadError as error:
            result = None
            ocr_error = error
        except Exception:
            await self.line.reply_text(reply_token, "画像の取得中にエラーが発生しました。もう一度送信してください。")
            raise

        try:
            profile = await self.line.get_group_member_profile(group_id, user_id)
            display_name = profile.get("displayName", "LINEユーザー")
        except Exception:
            display_name = "LINEユーザー"

        group = await asyncio.to_thread(self.sheets.find_group, group_id)
        if not group:
            await asyncio.to_thread(
                self.sheets.append_import,
                ImportRecord(
                    message_id, group_id, "", user_id, display_name, "", "", "", None,
                    None, "unknown_group", "未登録のLINEグループです。管理画面でリーグを設定してください。", received_at,
                ),
            )
            await self.line.reply_text(reply_token, "このグループは未登録です。管理者にリーグ設定を依頼してください。")
            return

        mapping = await asyncio.to_thread(self.sheets.find_user, user_id, group.league)
        if not mapping:
            await asyncio.to_thread(
                self.sheets.append_import,
                ImportRecord(
                    message_id, group_id, group.group_name, user_id, display_name, "", group.league,
                    "", None, None, "unknown_user", "LINEユーザーと選手名の対応が未登録です。", received_at,
                ),
            )
            await self.line.reply_text(reply_token, "選手名との対応付けが未登録です。管理者に登録を依頼してください。")
            return

        if ocr_error:
            room_id = ocr_error.room_id if isinstance(ocr_error, ScoreReadError) else ""
            status = "awaiting_score_input" if room_id else "ocr_failed"
            await asyncio.to_thread(
                self.sheets.append_import,
                ImportRecord(
                    message_id, group_id, group.group_name, user_id, display_name, mapping.player_name,
                    group.league, room_id, None, None, status, str(ocr_error), received_at,
                ),
            )
            if room_id:
                await asyncio.to_thread(
                    self.sheets.append_pending_score_input,
                    PendingScoreInput(
                        message_id, group_id, user_id, mapping.player_name, group.league, room_id, received_at
                    ),
                )
                await self.line.reply_text(
                    reply_token,
                    "結果画面（部屋ID: " + room_id + "）は認識しましたが、収支を確定できませんでした。\n"
                    "元の収支を次の形式で送ってください。\n"
                    "入力 -4400\n"
                    "※アプリ画面に表示された換算前の符号付き数値を入力してください。",
                )
            else:
                await self.line.reply_text(reply_token, f"画像を読み取れませんでした。\n{ocr_error}\n結果画面全体が見える画像を送ってください。")
            return

        assert result is not None
        converted_score = convert_score(result.raw_score, group.rate_divisor)

        await asyncio.to_thread(
            self.sheets.append_score, mapping.player_name, converted_score, group.league, received_at
        )
        await asyncio.to_thread(
            self.sheets.append_import,
            ImportRecord(
                message_id, group_id, group.group_name, user_id, display_name, mapping.player_name,
                group.league, result.room_id, result.raw_score, converted_score, "recorded", "", received_at,
            ),
        )
        balance_notice = await self._monthly_balance_notice(group_id, received_at)
        await self.line.reply_text(
            reply_token,
            f"記録しました。\n{mapping.player_name}: {converted_score:+,}pt\n部屋ID: {result.room_id}\n{balance_notice}",
        )

    async def process_text_event(self, event: dict) -> None:
        """グループ設定と既存選手名へのLINEユーザーID対応付けを受け付ける。"""
        message = event.get("message", {})
        text = str(message.get("text", "")).strip()
        reply_token = event.get("replyToken", "")
        source = event.get("source", {})
        group_id = source.get("groupId", "")
        user_id = source.get("userId", "")
        if not group_id or not user_id:
            return

        manual_input = _parse_manual_score_input(text)
        if manual_input:
            room_id, raw_score = manual_input
            group = await asyncio.to_thread(self.sheets.find_group, group_id)
            if not group:
                await self.line.reply_text(reply_token, "このグループは未設定です。")
                return
            pending = await asyncio.to_thread(
                self.sheets.find_pending_score_input, group_id, user_id, room_id
            )
            if not pending:
                await self.line.reply_text(
                    reply_token,
                    "収支の手入力待ち画像が見つかりません。\n"
                    "画像の案内にある形式で「入力 数値」を送ってください。",
                )
                return
            converted_score = convert_score(raw_score, group.rate_divisor)
            recorded_at = jst_timestamp()
            await asyncio.to_thread(
                self.sheets.append_score, pending.player_name, converted_score, pending.league, recorded_at
            )
            await asyncio.to_thread(self.sheets.resolve_pending_score_input, pending.message_id)
            await asyncio.to_thread(
                self.sheets.append_import,
                ImportRecord(
                    f"{pending.message_id}:manual", group_id, group.group_name, user_id, "",
                    pending.player_name, pending.league, pending.room_id, raw_score, converted_score,
                    "manual_recorded", "LINE手入力で補完", recorded_at,
                ),
            )
            balance_notice = await self._monthly_balance_notice(group_id, recorded_at)
            await self.line.reply_text(
                reply_token,
                f"手入力で記録しました。\n{pending.player_name}: {converted_score:+,}pt\n"
                f"部屋ID: {pending.room_id}\n{balance_notice}",
            )
            return

        direct_manual_input = _parse_direct_manual_input(text)
        if direct_manual_input:
            requested_name, raw_score = direct_manual_input
            group = await asyncio.to_thread(self.sheets.find_group, group_id)
            if not group:
                await self.line.reply_text(reply_token, "このグループは未設定です。")
                return
            player_name = await asyncio.to_thread(
                self.sheets.find_player_name, group.league, requested_name
            )
            if not player_name:
                await self.line.reply_text(
                    reply_token,
                    f"「{requested_name}」は{group.league}の選手名として見つかりません。台帳の表記を確認してください。",
                )
                return
            converted_score = convert_score(raw_score, group.rate_divisor)
            recorded_at = jst_timestamp()
            message_id = str(message.get("id", ""))
            await asyncio.to_thread(
                self.sheets.append_score, player_name, converted_score, group.league, recorded_at
            )
            await asyncio.to_thread(
                self.sheets.append_import,
                ImportRecord(
                    f"{message_id}:direct-manual", group_id, group.group_name, user_id, "",
                    player_name, group.league, "", raw_score, converted_score,
                    "manual_recorded", "結果画像なしのLINE手動入力", recorded_at,
                ),
            )
            await self.line.reply_text(
                reply_token,
                f"手動で記録しました。\n{player_name}: {converted_score:+,}pt\n"
                + await self._monthly_balance_notice(group_id, recorded_at),
            )
            return

        setup = re.fullmatch(r"設定\s*(.+?)(?:\s+([1-9]\d*))?\s*", text)
        if setup:
            league = setup.group(1).strip()
            divisor = int(setup.group(2) or "30")
            if not await asyncio.to_thread(self.sheets.league_exists, league):
                await self.line.reply_text(reply_token, f"「{league}」は台帳に存在しないリーグです。")
                return
            await asyncio.to_thread(self.sheets.upsert_group, GroupConfig(group_id, "", league, divisor, True))
            await self.line.reply_text(
                reply_token,
                f"このグループを設定しました。\nリーグ: {league}\n換算率: 1/{divisor}\n続けて「登録 選手名」を送ってください。",
            )
            return

        registration = re.fullmatch(r"登録\s*(.+)", text)
        if not registration:
            return

        group = await asyncio.to_thread(self.sheets.find_group, group_id)
        if not group:
            await self.line.reply_text(
                reply_token,
                "このグループは未設定です。管理者が「設定 リーグ名 換算率」を送ってください。\n例: 設定 漢気リーグ 30",
            )
            return

        requested_name = registration.group(1).strip()
        player_name = await asyncio.to_thread(self.sheets.find_player_name, group.league, requested_name)
        if not player_name:
            await self.line.reply_text(
                reply_token,
                f"「{requested_name}」は{group.league}の選手名として見つかりません。台帳の表記を確認してください。",
            )
            return

        try:
            profile = await self.line.get_group_member_profile(group_id, user_id)
            display_name = profile.get("displayName", "LINEユーザー")
        except Exception:
            display_name = "LINEユーザー"
        await asyncio.to_thread(
            self.sheets.upsert_user,
            UserMapping(user_id, display_name, player_name, group.league, True),
        )
        await self.line.reply_text(
            reply_token,
            f"登録しました。\nLINE表示名: {display_name}\n選手名: {player_name}\nリーグ: {group.league}",
        )

    async def _monthly_balance_notice(self, group_id: str, recorded_at: str) -> str:
        year_month = recorded_at[:7]
        total = await asyncio.to_thread(self.sheets.month_total, group_id, year_month)
        year, month = year_month.split("-")
        label = f"{int(year)}年{int(month)}月"
        if total == 0:
            return f"✅ {label}の合計ポイントは 0 です。"
        return f"⚠️ {label}の合計ポイントは {total:+,}pt です。今月の記録を確認してください。"


def _parse_manual_score_input(text: str) -> tuple[str | None, int] | None:
    """`入力 -4400` を読む。部屋ID付き入力も過去の案内との互換性のため受け付ける。"""
    normalized = unicodedata.normalize("NFKC", text).translate(
        str.maketrans({"−": "-", "ー": "-", "―": "-", "‐": "-", "–": "-", "—": "-"})
    )
    match = re.fullmatch(r"入力\s+(?:(\d{3,})\s+)?([+-])\s*([0-9][0-9,\s]{0,14})\s*", normalized)
    if not match:
        return None
    room_id, sign, digits = match.groups()
    amount = int(re.sub(r"[^0-9]", "", digits))
    if amount == 0:
        return None
    return room_id, amount if sign == "+" else -amount


def _parse_direct_manual_input(text: str) -> tuple[str, int] | None:
    """結果画像がない場合の `手動入力 選手名 -4400` を読む。"""
    normalized = unicodedata.normalize("NFKC", text).translate(
        str.maketrans({"−": "-", "ー": "-", "―": "-", "‐": "-", "–": "-", "—": "-"})
    )
    match = re.fullmatch(
        r"(?:手動入力|手入力)\s+(.+?)\s+([+-])\s*([0-9][0-9,\s]{0,14})\s*", normalized
    )
    if not match:
        return None
    player_name, sign, digits = match.groups()
    amount = int(re.sub(r"[^0-9]", "", digits))
    if amount == 0:
        return None
    return player_name.strip(), amount if sign == "+" else -amount
