from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """実行環境から読み込む設定値。秘密情報はリポジトリに保存しない。"""

    spreadsheet_id: str
    line_channel_secret: str
    line_channel_access_token: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            spreadsheet_id=os.getenv(
                "SPREADSHEET_ID", "1YLXZWQ6XZz04mi0dx9_6WFbm2-yZQGGIXd3yVEh9kTQ"
            ),
            line_channel_secret=os.getenv("LINE_CHANNEL_SECRET", ""),
            line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""),
        )

    def validate_for_webhook(self) -> None:
        missing = [
            name
            for name, value in (
                ("LINE_CHANNEL_SECRET", self.line_channel_secret),
                ("LINE_CHANNEL_ACCESS_TOKEN", self.line_channel_access_token),
                ("SPREADSHEET_ID", self.spreadsheet_id),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"環境変数が未設定です: {', '.join(missing)}")

