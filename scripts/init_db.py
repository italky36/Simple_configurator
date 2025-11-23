import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(models.CoffeeMachine).count()
        if existing > 0:
            print(f"Database already initialized with {existing} record(s); skipping seed.")
            return

        seed_items = [
            {
                "name": "CM-100",
                "model": "CM-100",
                "frame": "Metal",
                "frame_color": "Black",
                "refrigerator": "Yes",
                "terminal": "PAX",
                "price": 120000,
                "ozon_link": "https://example.com/ozon/cm-100",
                "graphic_link": "https://example.com/graphics/cm-100.png",
                "main_image": "https://example.com/images/cm-100-main.jpg",
                "gallery_folder": "/gallery/cm-100",
                "description": "Entry-level coffee machine.",
            },
            {
                "name": "CM-200",
                "model": "CM-200",
                "frame": "Metal",
                "frame_color": "Silver",
                "refrigerator": "Yes",
                "terminal": "Ingenico",
                "price": 150000,
                "ozon_link": "https://example.com/ozon/cm-200",
                "graphic_link": "https://example.com/graphics/cm-200.png",
                "main_image": "https://example.com/images/cm-200-main.jpg",
                "gallery_folder": "/gallery/cm-200",
                "description": "Mid-tier machine with larger hopper.",
            },
        ]

        for item in seed_items:
            db.add(models.CoffeeMachine(**item))
        db.commit()
        print(f"Initialized DB and inserted {len(seed_items)} record(s).")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
