"""
Обновление кеша картинок (main + gallery) для всех записей.

Запуск из корня проекта:
  python -m scripts.refresh_media_cache
  # или
  python scripts/refresh_media_cache.py
"""

import sys
from pathlib import Path

# Добавляем корень проекта и каталог app в sys.path, если запускают напрямую
ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
for p in (ROOT, APP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.config import Settings
from app.database import SessionLocal, engine
from app.seafile_client import SeafileClient
from app.services import media_cache
from app import crud
from sqlalchemy import inspect


def ensure_main_image_path_column() -> None:
    # Быстрая миграция: добавляем колонку, если её нет
    insp = inspect(engine)
    cols = [c["name"] for c in insp.get_columns("coffee_machines")]
    if "main_image_path" in cols:
        return
    ddl = "ALTER TABLE coffee_machines ADD COLUMN main_image_path VARCHAR(500)"
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.exec_driver_sql(ddl)


def main() -> None:
    settings = Settings()
    ensure_main_image_path_column()
    db = SessionLocal()
    client = SeafileClient(settings.seafile_server, settings.seafile_repo_id, settings.seafile_token)

    machines = crud.get_coffee_machines(db, limit=10_000)
    total = len(machines)
    refreshed = 0
    updated_db = 0

    for m in machines:
        try:
            media_cache.cache_machine_media(m, client)
            refreshed += 1

            cached_main = media_cache.get_cached_main(m.id)
            cached_gallery = media_cache.get_cached_gallery(m.id)

            # Если main не удалось скачать (старый токен), но есть галерея — ставим первую из галереи как main
            if not cached_main and cached_gallery:
                cached_main = cached_gallery[0]

            if cached_main and m.main_image != cached_main:
                m.main_image = cached_main
                db.add(m)
                db.commit()
                updated_db += 1

            print(f"[OK] id={m.id} model={m.model or m.name} cached_main={'yes' if cached_main else 'no'} gallery={len(cached_gallery)}")
        except Exception as exc:
            print(f"[FAIL] id={m.id} model={m.model or m.name}: {exc}")

    db.close()
    print(f"Done: {refreshed}/{total} refreshed, main_image updated in DB: {updated_db}")


if __name__ == "__main__":
    main()
