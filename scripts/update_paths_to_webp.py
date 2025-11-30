#!/usr/bin/env python3
"""
Обновляет пути в базе данных с .svg на .webp после конвертации файлов.

Использование:
    python scripts/update_paths_to_webp.py

Опции:
    --dry-run    Показать что будет изменено, но не сохранять
    --reverse    Обратная операция: .webp → .svg
"""

import sys
import argparse
from pathlib import Path

# Добавляем корневую директорию в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import SessionLocal
from app.models import CoffeeMachine


def update_image_paths(
    old_ext: str = '.svg',
    new_ext: str = '.webp',
    dry_run: bool = False
) -> dict:
    """
    Обновляет расширения файлов в design_images.

    Args:
        old_ext: Старое расширение (напр. '.svg')
        new_ext: Новое расширение (напр. '.webp')
        dry_run: Если True, только показать изменения без сохранения

    Returns:
        Статистика обновлений
    """

    db = SessionLocal()
    stats = {
        'machines_checked': 0,
        'machines_updated': 0,
        'images_updated': 0,
        'changes': []
    }

    try:
        machines = db.query(CoffeeMachine).all()
        stats['machines_checked'] = len(machines)

        for machine in machines:
            if not machine.design_images:
                continue

            machine_updated = False
            changes_for_machine = []

            # Проходим по всем цветам каркаса и вставок
            for frame_color, insert_colors in machine.design_images.items():
                if not isinstance(insert_colors, dict):
                    continue

                for insert_color, image_data in insert_colors.items():
                    if not isinstance(image_data, dict):
                        continue

                    # Обновляем main_image если есть
                    if 'main_image' in image_data and image_data['main_image']:
                        old_path = image_data['main_image']
                        if old_path.endswith(old_ext):
                            new_path = old_path[:-len(old_ext)] + new_ext
                            image_data['main_image'] = new_path
                            machine_updated = True
                            stats['images_updated'] += 1
                            changes_for_machine.append({
                                'frame_color': frame_color,
                                'insert_color': insert_color,
                                'field': 'main_image',
                                'old': old_path,
                                'new': new_path
                            })

                    # Обновляем gallery_folder если есть (может содержать пути к файлам)
                    # Обычно это просто путь к папке, но на всякий случай проверим
                    if 'gallery_folder' in image_data and image_data['gallery_folder']:
                        old_path = image_data['gallery_folder']
                        if old_path.endswith(old_ext):
                            new_path = old_path[:-len(old_ext)] + new_ext
                            image_data['gallery_folder'] = new_path
                            machine_updated = True
                            changes_for_machine.append({
                                'frame_color': frame_color,
                                'insert_color': insert_color,
                                'field': 'gallery_folder',
                                'old': old_path,
                                'new': new_path
                            })

            if machine_updated:
                stats['machines_updated'] += 1
                stats['changes'].append({
                    'machine_id': machine.id,
                    'machine_name': machine.name,
                    'changes': changes_for_machine
                })

                if not dry_run:
                    # SQLAlchemy автоматически отслеживает изменения в JSON полях
                    # но для надёжности явно помечаем как изменённое
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(machine, "design_images")

        if not dry_run:
            db.commit()
            print("✅ Изменения сохранены в базе данных")
        else:
            print("🔍 Режим предпросмотра (изменения НЕ сохранены)")

    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка: {e}")
        raise
    finally:
        db.close()

    return stats


def print_stats(stats: dict, old_ext: str, new_ext: str):
    """Выводит статистику обновлений."""

    print("\n" + "=" * 70)
    print("📊 Результаты обновления путей")
    print("=" * 70)
    print(f"Проверено машин: {stats['machines_checked']}")
    print(f"Обновлено машин: {stats['machines_updated']}")
    print(f"Обновлено изображений: {stats['images_updated']}")
    print()

    if stats['changes']:
        print("📝 Детали изменений:")
        print("-" * 70)

        for change_group in stats['changes']:
            print(f"\n🔧 Машина #{change_group['machine_id']}: {change_group['machine_name']}")

            for change in change_group['changes']:
                frame = change['frame_color']
                insert = change['insert_color']
                field = change['field']
                print(f"   [{frame}][{insert}][{field}]:")
                print(f"   - Было: {Path(change['old']).name}")
                print(f"   - Стало: {Path(change['new']).name}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Обновляет пути к изображениям в базе данных'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Показать изменения без сохранения в БД'
    )
    parser.add_argument(
        '--reverse',
        action='store_true',
        help='Обратная операция: .webp → .svg'
    )

    args = parser.parse_args()

    if args.reverse:
        old_ext = '.webp'
        new_ext = '.svg'
        print("🔄 Обратная конвертация: .webp → .svg")
    else:
        old_ext = '.svg'
        new_ext = '.webp'
        print("🔄 Конвертация путей: .svg → .webp")

    print()

    stats = update_image_paths(
        old_ext=old_ext,
        new_ext=new_ext,
        dry_run=args.dry_run
    )

    print_stats(stats, old_ext, new_ext)

    if args.dry_run:
        print("\n💡 Для применения изменений запустите без --dry-run")


if __name__ == "__main__":
    main()
