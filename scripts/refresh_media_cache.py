"""
Обновление кеша картинок (main + gallery) для всех записей.

Запуск: python scripts/refresh_media_cache.py
"""

from app.config import Settings
from app.database import SessionLocal
from app.seafile_client import SeafileClient
from app.services import media_cache
from app import crud


def main() -> None:
    settings = Settings()
    db = SessionLocal()
    client = SeafileClient(settings.seafile_server, settings.seafile_repo_id, settings.seafile_token)

    machines = crud.get_coffee_machines(db, limit=10_000)
    total = len(machines)
    refreshed = 0

    for m in machines:
        try:
            media_cache.cache_machine_media(m, client)
            refreshed += 1
            print(f"[OK] id={m.id} model={m.model or m.name}")
        except Exception as exc:
            print(f"[FAIL] id={m.id} model={m.model or m.name}: {exc}")

    db.close()
    print(f"Done: {refreshed}/{total} refreshed")


if __name__ == "__main__":
    main()
