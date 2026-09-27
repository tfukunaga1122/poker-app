from __future__ import annotations

from .config import Settings
from .sheets import SheetsRepository


def main() -> None:
    settings = Settings.from_env()
    created = SheetsRepository(settings.spreadsheet_id).ensure_schema()
    if created:
        print("作成したシート: " + ", ".join(created))
    else:
        print("必要なシートはすでに作成済みです。")


if __name__ == "__main__":
    main()

