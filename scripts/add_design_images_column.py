import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.database import engine
from sqlalchemy import text


def add_design_images_column():
    """Добавляет столбец design_images в таблицу coffee_machines"""
    with engine.connect() as conn:
        try:
            # Проверяем, существует ли уже столбец
            result = conn.execute(text("PRAGMA table_info(coffee_machines)"))
            columns = [row[1] for row in result]

            if 'design_images' in columns:
                print("Столбец design_images уже существует")
                return

            # Добавляем новый столбец
            conn.execute(text("ALTER TABLE coffee_machines ADD COLUMN design_images TEXT"))
            conn.commit()
            print("Столбец design_images успешно добавлен")
        except Exception as e:
            print(f"Ошибка при добавлении столбца: {e}")
            raise


if __name__ == "__main__":
    add_design_images_column()
