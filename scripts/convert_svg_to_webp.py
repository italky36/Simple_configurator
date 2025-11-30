#!/usr/bin/env python3
"""
Конвертирует SVG файлы в WebP формат для уменьшения размера.

SVG рендерится в высоком разрешении (по умолчанию 2000px по ширине)
и сохраняется как WebP с хорошим сжатием.

Требования:
    pip install pillow cairosvg

Использование:
    # Конвертировать один файл
    python scripts/convert_svg_to_webp.py app/static/cache/machines/10/design_white_blue.svg

    # Конвертировать все SVG в директории
    python scripts/convert_svg_to_webp.py app/static/cache/machines/10/

    # Указать разрешение (ширина в пикселях)
    python scripts/convert_svg_to_webp.py --width 3000 app/static/cache/machines/10/
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

try:
    import cairosvg
    from PIL import Image
    import io
except ImportError:
    print("❌ Требуются библиотеки: pip install pillow cairosvg")
    sys.exit(1)


def svg_to_webp(
    svg_path: Path,
    output_path: Optional[Path] = None,
    width: int = 2000,
    quality: int = 85,
    keep_original: bool = True
) -> Optional[Path]:
    """
    Конвертирует SVG файл в WebP.

    Args:
        svg_path: Путь к SVG файлу
        output_path: Путь для сохранения WebP (если None, заменяет расширение)
        width: Ширина изображения в пикселях (высота вычисляется пропорционально)
        quality: Качество WebP (0-100, рекомендуется 80-90)
        keep_original: Сохранить оригинальный SVG файл

    Returns:
        Путь к созданному WebP файлу или None при ошибке
    """

    if not svg_path.exists():
        print(f"❌ Файл не найден: {svg_path}")
        return None

    if output_path is None:
        output_path = svg_path.with_suffix('.webp')

    try:
        # Читаем SVG
        svg_data = svg_path.read_bytes()

        # Конвертируем SVG в PNG в памяти с заданной шириной
        png_data = cairosvg.svg2png(
            bytestring=svg_data,
            output_width=width
        )

        # Загружаем PNG из памяти
        image = Image.open(io.BytesIO(png_data))

        # Сохраняем как WebP
        image.save(
            output_path,
            'WEBP',
            quality=quality,
            method=6  # Лучшее сжатие (медленнее, но меньше размер)
        )

        # Статистика
        original_size = svg_path.stat().st_size
        webp_size = output_path.stat().st_size
        reduction = (1 - webp_size / original_size) * 100

        print(f"✓ {svg_path.name}")
        print(f"  {original_size:,} → {webp_size:,} байт ({reduction:.1f}% уменьшение)")
        print(f"  Разрешение: {image.width}x{image.height}px")

        # Удаляем оригинал если нужно
        if not keep_original:
            svg_path.unlink()
            print(f"  🗑️  Удалён оригинал SVG")

        return output_path

    except Exception as e:
        print(f"❌ Ошибка при конвертации {svg_path.name}: {e}")
        return None


def convert_directory(
    directory: Path,
    width: int = 2000,
    quality: int = 85,
    keep_original: bool = True,
    recursive: bool = False
) -> dict:
    """
    Конвертирует все SVG файлы в директории.

    Returns:
        Словарь со статистикой конвертации
    """

    pattern = "**/*.svg" if recursive else "*.svg"
    svg_files = list(directory.glob(pattern))

    if not svg_files:
        print(f"⚠️  SVG файлы не найдены в {directory}")
        return {}

    print(f"📁 Найдено {len(svg_files)} SVG файлов\n")

    stats = {
        'total': len(svg_files),
        'converted': 0,
        'failed': 0,
        'original_size': 0,
        'webp_size': 0
    }

    for svg_path in svg_files:
        original_size = svg_path.stat().st_size
        stats['original_size'] += original_size

        webp_path = svg_to_webp(
            svg_path,
            width=width,
            quality=quality,
            keep_original=keep_original
        )

        if webp_path and webp_path.exists():
            stats['converted'] += 1
            stats['webp_size'] += webp_path.stat().st_size
        else:
            stats['failed'] += 1

        print()  # Пустая строка между файлами

    return stats


def print_summary(stats: dict):
    """Выводит итоговую статистику."""

    if not stats:
        return

    print("=" * 70)
    print("📊 Итоги конвертации:")
    print("=" * 70)
    print(f"Всего файлов: {stats['total']}")
    print(f"Конвертировано: {stats['converted']}")
    print(f"Ошибок: {stats['failed']}")
    print()
    print(f"Исходный размер: {stats['original_size']:,} байт ({stats['original_size']/(1024*1024):.1f} MB)")
    print(f"Размер WebP: {stats['webp_size']:,} байт ({stats['webp_size']/(1024*1024):.1f} MB)")

    if stats['original_size'] > 0:
        reduction = (1 - stats['webp_size'] / stats['original_size']) * 100
        saved = stats['original_size'] - stats['webp_size']
        print(f"Сэкономлено: {saved:,} байт ({saved/(1024*1024):.1f} MB, {reduction:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description='Конвертирует SVG файлы в WebP формат'
    )
    parser.add_argument(
        'path',
        type=str,
        help='Путь к SVG файлу или директории'
    )
    parser.add_argument(
        '--width',
        type=int,
        default=2000,
        help='Ширина изображения в пикселях (по умолчанию: 2000)'
    )
    parser.add_argument(
        '--quality',
        type=int,
        default=85,
        help='Качество WebP 0-100 (по умолчанию: 85)'
    )
    parser.add_argument(
        '--delete-original',
        action='store_true',
        help='Удалить оригинальные SVG файлы после конвертации'
    )
    parser.add_argument(
        '--recursive',
        '-r',
        action='store_true',
        help='Обрабатывать поддиректории рекурсивно'
    )

    args = parser.parse_args()
    path = Path(args.path)

    if not path.exists():
        print(f"❌ Путь не найден: {path}")
        sys.exit(1)

    keep_original = not args.delete_original

    if path.is_file():
        # Конвертируем один файл
        svg_to_webp(
            path,
            width=args.width,
            quality=args.quality,
            keep_original=keep_original
        )
    elif path.is_dir():
        # Конвертируем директорию
        stats = convert_directory(
            path,
            width=args.width,
            quality=args.quality,
            keep_original=keep_original,
            recursive=args.recursive
        )
        print_summary(stats)
    else:
        print(f"❌ Неизвестный тип пути: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
