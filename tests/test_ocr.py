from app.models import convert_score
from app.ocr import (
    OCRReadError,
    extract_result_from_positioned_words,
    extract_result_from_text,
    is_result_screen_text,
)


def test_extracts_room_id_and_positive_score() -> None:
    result = extract_result_from_text("部屋ID 916809\n収支 +62,500")

    assert result.room_id == "916809"
    assert result.raw_score == 62500


def test_extracts_full_width_negative_score() -> None:
    result = extract_result_from_text("部屋ID：９１６８０９\n収支 －１２，３４５")

    assert result.room_id == "916809"
    assert result.raw_score == -12345


def test_extracts_room_id_when_vision_separates_label_and_value() -> None:
    text = "今回の成績\n部屋ID\n部屋名\n916809\nたくみっちの部屋\n収支\n+62,500"

    result = extract_result_from_text(text)

    assert result.room_id == "916809"
    assert result.raw_score == 62500


def test_extracts_values_by_position_when_chat_scrambles_vision_text_order() -> None:
    words = [
        ("部屋", 112, 785), ("ID", 184, 783), ("761210", 638, 788),
        ("33300", 142, 1184), ("収支", 117, 1257), ("+15,100", 570, 1261),
    ]

    result = extract_result_from_positioned_words(words, "scrambled OCR text")

    assert result.room_id == "761210"
    assert result.raw_score == 15100


def test_extracts_split_score_label_and_split_minus_value() -> None:
    """実機画像でVisionが「収」「支」「-」「4,400」に分けるケース。"""
    words = [
        ("部屋", 112, 785), ("ID", 184, 783), ("532168", 638, 788),
        ("収", 117, 1257), ("支", 163, 1258), ("−", 570, 1261), ("4,400", 604, 1260),
    ]

    result = extract_result_from_positioned_words(words, "split OCR text")

    assert result.room_id == "532168"
    assert result.raw_score == -4400


def test_extracts_dash_variant_from_text() -> None:
    result = extract_result_from_text("今回の成績\n部屋ID 272007\n収 支 −17,000")

    assert result.room_id == "272007"
    assert result.raw_score == -17000


def test_extracts_zero_score_without_sign() -> None:
    result = extract_result_from_text("今回の成績\n部屋ID 210606\n収支 0")

    assert result.room_id == "210606"
    assert result.raw_score == 0


def test_extracts_score_when_score_label_is_missing_from_positioned_ocr() -> None:
    words = [
        ("今回の績", 290, 410), ("部屋", 112, 785), ("ID", 184, 783),
        ("996440", 638, 788), ("+", 570, 1261), ("16,200", 604, 1260),
    ]

    result = extract_result_from_positioned_words(words, "今回の績")

    assert result.room_id == "996440"
    assert result.raw_score == 16200


def test_rejects_image_without_required_labels() -> None:
    try:
        extract_result_from_text("+62,500")
    except OCRReadError as error:
        assert "部屋ID" in str(error)
    else:
        raise AssertionError("OCRReadError が発生する必要があります")


def test_identifies_only_result_screen_text() -> None:
    assert is_result_screen_text("今回の成績\n部屋ID 916809\n収支 +62,500")
    assert is_result_screen_text("最良ハンド フルハウス\n収支 -6,300")
    assert not is_result_screen_text("旅行の写真\n集合は19時です")


def test_score_conversion_matches_existing_app() -> None:
    assert convert_score(62500, 30) == 2080
    assert convert_score(-62500, 30) == -2080
    assert convert_score(29, 30) == 0
