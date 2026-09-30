from __future__ import annotations

import re
import threading
import unicodedata
from typing import Any

from .models import OCRResult


class OCRReadError(ValueError):
    """結果画面として必要な項目を読み取れなかった場合の例外。"""


class NotResultScreenError(OCRReadError):
    """ポーカー結果画面ではないため、通知・記録を行わずに無視する画像。"""


class ScoreReadError(OCRReadError):
    """結果画面と部屋IDは判別できたが、収支だけを確定できない場合の例外。"""

    def __init__(self, room_id: str, message: str = "「収支」の符号付き数値を読み取れませんでした。") -> None:
        super().__init__(message)
        self.room_id = room_id


_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９＋－，", "0123456789+-,")
_DASH_VARIANTS = str.maketrans({"−": "-", "ー": "-", "―": "-", "‐": "-", "–": "-", "—": "-"})
# Vision OCRでは「部屋ID」と値の間に改行・「部屋名」など別の項目が挿入される
# ことがある。ラベル後の次の数値を、十分短い範囲で許容して取得する。
_ROOM_ID = re.compile(r"部\s*屋\s*(?:I|1|\|)\s*D[^0-9]{0,80}?([0-9]{3,})", re.IGNORECASE)
_SCORE = re.compile(
    r"収\s*支[^+\-0-9]{0,24}([+\-])\s*([0-9][0-9,\s]{0,14})"
)
_ZERO_SCORE = re.compile(r"収\s*支[^0-9]{0,24}0(?:[0,\s]*)")
_SIGNED_NUMBER = re.compile(r"^([+\-])\s*([0-9][0-9,\s]{0,14})$")
# 結果画面の装飾文字はVisionで「今回の績」のように一部が欠けることがある。
_RESULT_TITLE = re.compile(r"今\s*回(?:\s*の)?\s*(?:成\s*)?績")
_ROOM_LABEL = re.compile(r"部\s*屋\s*(?:I|1|\|)\s*D", re.IGNORECASE)
_SCORE_LABEL = re.compile(r"収\s*支")
_HAND_LABEL = re.compile(r"最\s*良\s*ハ\s*ン\s*ド")
_BLIND_LABEL = re.compile(r"S\s*B\s*/\s*B\s*B", re.IGNORECASE)

# ImageAnnotatorClient はgRPC接続と認証情報を保持するため、画像ごとに作成すると
# 同時投稿時にコンテナのメモリを急増させてしまう。プロセス内で1つだけ再利用する。
_vision_client: Any | None = None
_vision_client_lock = threading.Lock()


def _normalize(value: str) -> str:
    """全半角とVisionが使いがちなマイナス記号の違いを吸収する。"""
    return unicodedata.normalize("NFKC", value).translate(_FULLWIDTH_DIGITS).translate(_DASH_VARIANTS)


def _score_from_value(value: str) -> int | None:
    normalized = _normalize(value)
    # アプリでは収支0だけ符号なしで表示される。
    if re.fullmatch(r"0[0,\s]*", normalized):
        return 0
    match = _SIGNED_NUMBER.fullmatch(normalized)
    if not match:
        return None
    sign, digits = match.groups()
    amount = int(re.sub(r"[^0-9]", "", digits))
    return amount if sign == "+" else -amount


def _get_vision_client() -> Any:
    global _vision_client
    if _vision_client is None:
        with _vision_client_lock:
            if _vision_client is None:
                from google.cloud import vision

                _vision_client = vision.ImageAnnotatorClient()
    return _vision_client


def extract_result_from_text(text: str) -> OCRResult:
    """Vision OCRの文字列から部屋IDと符号付き収支を取り出す。"""
    normalized = _normalize(text)
    room_match = _ROOM_ID.search(normalized)
    score_match = _SCORE.search(normalized)
    if not room_match:
        raise OCRReadError("部屋IDを読み取れませんでした。")
    if not score_match:
        if _ZERO_SCORE.search(normalized):
            return OCRResult(room_id=room_match.group(1), raw_score=0, source_text=normalized)
        raise ScoreReadError(room_match.group(1))

    sign, digits = score_match.groups()
    amount = int(re.sub(r"[^0-9]", "", digits))
    return OCRResult(
        room_id=room_match.group(1),
        raw_score=amount if sign == "+" else -amount,
        source_text=normalized,
    )


def is_result_screen_text(text: str) -> bool:
    """結果画面特有の見出しがある画像だけを記録対象にする。"""
    normalized = _normalize(text)
    # 結果画面はOCRの状況により一部の見出しが欠ける。タイトル・最良ハンドは
    # 結果画面に固有なので単独でも採用し、それ以外は2つの見出しがそろう場合だけ採用する。
    if _RESULT_TITLE.search(normalized) or _HAND_LABEL.search(normalized):
        return True
    return bool(_ROOM_LABEL.search(normalized) and _SCORE_LABEL.search(normalized))


def extract_result_from_positioned_words(
    words: list[tuple[str, int, int]], source_text: str
) -> OCRResult:
    """画面上の位置から、部屋ID・収支ラベルと同じ行の値を取得する。

    結果画面にチャットが重なった場合、Visionの全文テキストは画面順にならない。
    ラベルの右側かつ近いY座標にある数値を使うことで、チャット中の数値を避ける。
    """
    normalized_words = [(_normalize(word), x, y) for word, x, y in words if word.strip()]

    def joined_label(index: int, parts: tuple[str, ...]) -> bool:
        """Visionがラベルを単語単位に分けた場合にも一致させる。"""
        joined = ""
        previous_x: int | None = None
        y = normalized_words[index][2]
        for word, x, candidate_y in normalized_words[index : index + len(parts)]:
            if abs(candidate_y - y) > 55 or (previous_x is not None and x - previous_x > 220):
                return False
            joined += word
            previous_x = x
        return joined.upper() == "".join(parts).upper()

    def label_positions(parts: tuple[str, ...], exact: str) -> list[tuple[int, int]]:
        positions: list[tuple[int, int]] = []
        for index, (word, x, y) in enumerate(normalized_words):
            if word.upper() == exact.upper() or joined_label(index, parts):
                positions.append((x, y))
        return positions

    room_labels = label_positions(("部屋", "ID"), "部屋ID")

    room_id = ""
    room_label_y: int | None = None
    for label_x, label_y in room_labels:
        candidates: list[tuple[int, int, str]] = []
        for word, x, y in normalized_words:
            if x <= label_x + 120 or abs(y - label_y) > 90:
                continue
            if re.fullmatch(r"[0-9]{3,}", word):
                candidates.append((abs(y - label_y), x, word))
        if candidates:
            room_id = min(candidates)[2]
            room_label_y = label_y
            break

    score_labels = label_positions(("収", "支"), "収支")
    raw_score: int | None = None
    for label_x, label_y in score_labels:
        candidates: list[tuple[int, int, int]] = []
        for index, (word, x, y) in enumerate(normalized_words):
            if x <= label_x + 100 or abs(y - label_y) > 90:
                continue
            value = _score_from_value(word)
            if value is not None:
                candidates.append((abs(y - label_y), x, value))
                continue
            # 符号と数値を別の単語として返すVisionの結果を結合する。
            if word not in {"+", "-"}:
                continue
            for number, number_x, number_y in normalized_words[index + 1 : index + 4]:
                if number_x < x or number_x - x > 260 or abs(number_y - y) > 55:
                    continue
                value = _score_from_value(word + number)
                if value is not None:
                    candidates.append((abs(y - label_y), x, value))
                    break
        if candidates:
            raw_score = min(candidates)[2]
            break

    # 「収支」の装飾文字だけがOCRで欠けても、結果タイトル・部屋ID・下側の符号付き
    # 数値が揃えば、このアプリ固有の結果画面として安全に補完できる。
    if raw_score is None and room_label_y is not None:
        normalized_source = _normalize(source_text)
        has_result_heading = bool(_RESULT_TITLE.search(normalized_source) or _HAND_LABEL.search(normalized_source))
        if has_result_heading:
            candidates = []
            for index, (word, x, y) in enumerate(normalized_words):
                if y <= room_label_y + 120:
                    continue
                value = _score_from_value(word)
                if value is not None and word.startswith(("+", "-")):
                    candidates.append((y - room_label_y, x, value))
                    continue
                if word not in {"+", "-"}:
                    continue
                for number, number_x, number_y in normalized_words[index + 1 : index + 4]:
                    if number_x < x or number_x - x > 260 or abs(number_y - y) > 55:
                        continue
                    value = _score_from_value(word + number)
                    if value is not None:
                        candidates.append((y - room_label_y, x, value))
                        break
            if candidates:
                raw_score = min(candidates)[2]

    if not room_id:
        raise OCRReadError("部屋IDを読み取れませんでした。")
    if raw_score is None:
        raise ScoreReadError(room_id)
    return OCRResult(room_id=room_id, raw_score=raw_score, source_text=source_text)


def _positioned_words(annotation: Any) -> list[tuple[str, int, int]]:
    words: list[tuple[str, int, int]] = []
    for page in annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    text = "".join(symbol.text for symbol in word.symbols)
                    vertex = word.bounding_box.vertices[0]
                    words.append((text, vertex.x, vertex.y))
    return words


def read_result_image(image_bytes: bytes) -> OCRResult:
    """Google Cloud Vision OCRで結果画面を読み取る。"""
    # OCRを利用しないテストや管理画面の起動時に、Vision SDKを必須にしない。
    from google.cloud import vision

    client = _get_vision_client()
    response = client.document_text_detection(image=vision.Image(content=image_bytes))
    if response.error.message:
        raise OCRReadError(f"OCRサービスでエラーが発生しました: {response.error.message}")
    text = response.full_text_annotation.text if response.full_text_annotation else ""
    if not text.strip():
        raise NotResultScreenError("結果画面ではありません。")
    if not is_result_screen_text(text):
        raise NotResultScreenError("結果画面ではありません。")
    try:
        return extract_result_from_positioned_words(
            _positioned_words(response.full_text_annotation), text
        )
    except OCRReadError as positioned_error:
        try:
            return extract_result_from_text(text)
        except OCRReadError:
            # 部屋IDだけ読めた場合は、LINEで手入力を受け付けられるようにする。
            raise positioned_error
