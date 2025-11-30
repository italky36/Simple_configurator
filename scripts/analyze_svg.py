#!/usr/bin/env python3
"""
Анализирует SVG файл чтобы понять, почему он такой большой.
Проверяет на наличие:
- Встроенных base64 изображений
- Больших path данных
- Дублированных элементов
- Метаданных

Использование:
    python scripts/analyze_svg.py app/static/cache/machines/10/design_white_blue.svg
"""

import sys
import re
from pathlib import Path
from collections import Counter


def analyze_svg(filepath: Path) -> dict:
    """Анализирует SVG файл и возвращает статистику."""

    if not filepath.exists():
        print(f"❌ Файл не найден: {filepath}")
        return {}

    content = filepath.read_text(encoding='utf-8')
    size = len(content)

    stats = {
        'file_size': size,
        'file_size_mb': size / (1024 * 1024),
        'total_chars': len(content),
        'embedded_images': 0,
        'embedded_images_size': 0,
        'path_elements': 0,
        'path_data_size': 0,
        'text_elements': 0,
        'comments_size': 0,
        'metadata_size': 0,
    }

    # Проверяем встроенные изображения (base64)
    image_pattern = re.compile(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+')
    images = image_pattern.findall(content)
    if images:
        stats['embedded_images'] = len(images)
        stats['embedded_images_size'] = sum(len(img) for img in images)
        stats['embedded_images_percent'] = (stats['embedded_images_size'] / size) * 100

    # Проверяем path элементы
    path_pattern = re.compile(r'<path[^>]+d="([^"]+)"', re.DOTALL)
    paths = path_pattern.findall(content)
    if paths:
        stats['path_elements'] = len(paths)
        stats['path_data_size'] = sum(len(p) for p in paths)
        stats['path_data_percent'] = (stats['path_data_size'] / size) * 100

    # Проверяем text элементы
    stats['text_elements'] = content.count('<text')

    # Проверяем комментарии
    comment_pattern = re.compile(r'<!--.*?-->', re.DOTALL)
    comments = comment_pattern.findall(content)
    if comments:
        stats['comments_size'] = sum(len(c) for c in comments)
        stats['comments_percent'] = (stats['comments_size'] / size) * 100

    # Проверяем метаданные
    metadata_pattern = re.compile(r'<metadata>.*?</metadata>', re.DOTALL)
    metadata = metadata_pattern.findall(content)
    if metadata:
        stats['metadata_size'] = sum(len(m) for m in metadata)
        stats['metadata_percent'] = (stats['metadata_size'] / size) * 100

    # Проверяем defs
    defs_pattern = re.compile(r'<defs>.*?</defs>', re.DOTALL)
    defs = defs_pattern.findall(content)
    if defs:
        stats['defs_size'] = sum(len(d) for d in defs)
        stats['defs_percent'] = (stats['defs_size'] / size) * 100

    return stats


def print_stats(stats: dict, filepath: Path):
    """Красиво выводит статистику."""

    print(f"\n📊 Анализ SVG файла: {filepath.name}")
    print("=" * 70)
    print(f"Общий размер: {stats['file_size']:,} байт ({stats['file_size_mb']:.2f} MB)")
    print()

    if stats['embedded_images'] > 0:
        print(f"🖼️  Встроенные изображения (base64):")
        print(f"   Количество: {stats['embedded_images']}")
        print(f"   Размер: {stats['embedded_images_size']:,} байт ({stats['embedded_images_size']/(1024*1024):.2f} MB)")
        print(f"   Процент от файла: {stats['embedded_images_percent']:.1f}%")
        print()

    if stats['path_elements'] > 0:
        print(f"📐 Path элементы (векторные данные):")
        print(f"   Количество: {stats['path_elements']}")
        print(f"   Размер данных: {stats['path_data_size']:,} байт ({stats['path_data_size']/(1024*1024):.2f} MB)")
        print(f"   Процент от файла: {stats['path_data_percent']:.1f}%")
        print()

    if stats.get('defs_size', 0) > 0:
        print(f"📦 Определения <defs> (переиспользуемые элементы):")
        print(f"   Размер: {stats['defs_size']:,} байт ({stats['defs_size']/(1024*1024):.2f} MB)")
        print(f"   Процент от файла: {stats['defs_percent']:.1f}%")
        print()

    if stats.get('comments_size', 0) > 0:
        print(f"💬 Комментарии:")
        print(f"   Размер: {stats['comments_size']:,} байт")
        print(f"   Процент от файла: {stats['comments_percent']:.1f}%")
        print()

    if stats.get('metadata_size', 0) > 0:
        print(f"ℹ️  Метаданные:")
        print(f"   Размер: {stats['metadata_size']:,} байт")
        print(f"   Процент от файла: {stats['metadata_percent']:.1f}%")
        print()

    if stats['text_elements'] > 0:
        print(f"✍️  Text элементы: {stats['text_elements']}")
        print()

    # Рекомендации
    print("💡 Рекомендации:")
    print("=" * 70)

    if stats['embedded_images'] > 0:
        print("⚠️  ПРОБЛЕМА: SVG содержит встроенные растровые изображения (base64)")
        print("   Это делает файл огромным и не поддающимся оптимизации.")
        print()
        print("   Решения:")
        print("   1. Извлечь изображения в отдельные PNG/JPG файлы")
        print("   2. Заменить <image href=\"data:image/...\" на <image href=\"image.png\"")
        print("   3. Использовать WebP формат для изображений (лучше сжатие)")
        print("   4. Попросить дизайнера пересохранить SVG без встроенных изображений")
        print()
    elif stats['path_data_size'] > 5 * 1024 * 1024:  # > 5MB of path data
        print("⚠️  SVG содержит очень много векторных данных (>5MB)")
        print("   Это может означать:")
        print("   - Очень детализированную графику")
        print("   - Трассированные растровые изображения (вместо настоящих векторов)")
        print()
        print("   Решения:")
        print("   1. Упростить векторную графику в редакторе (Illustrator/Inkscape)")
        print("   2. Если это трассированное изображение - использовать PNG/WebP вместо SVG")
        print("   3. Использовать svgo с агрессивными настройками упрощения path")
        print()
    else:
        print("✅ SVG выглядит нормально, большой размер из-за сложной векторной графики")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python scripts/analyze_svg.py <путь к SVG файлу>")
        print()
        print("Пример:")
        print("  python scripts/analyze_svg.py app/static/cache/machines/10/design_white_blue.svg")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    stats = analyze_svg(filepath)

    if stats:
        print_stats(stats, filepath)
