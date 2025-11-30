#!/usr/bin/env python3
"""
Оптимизирует уже существующие SVG файлы в кэше.
Использует ту же функцию _optimize_svg из media_cache.

Использование:
    python scripts/optimize_cached_svg.py
"""
from pathlib import Path
import sys

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.media_cache import CACHE_ROOT, _optimize_svg


def main():
    cache_dir = Path(CACHE_ROOT)

    if not cache_dir.exists():
        print(f"❌ Кэш директория не найдена: {cache_dir}")
        return

    # Находим все SVG файлы
    svg_files = list(cache_dir.rglob("*.svg"))

    if not svg_files:
        print("ℹ️  SVG файлы не найдены в кэше")
        return

    print(f"🔍 Найдено {len(svg_files)} SVG файлов")
    print(f"📁 Путь: {cache_dir}\n")

    total_original = 0
    total_optimized = 0
    optimized_count = 0
    skipped_count = 0

    for i, svg_path in enumerate(svg_files, 1):
        original_size = svg_path.stat().st_size
        total_original += original_size

        print(f"[{i}/{len(svg_files)}] {svg_path.relative_to(cache_dir)}")
        print(f"  Original: {original_size:,} bytes")

        _optimize_svg(svg_path)

        new_size = svg_path.stat().st_size
        total_optimized += new_size

        if new_size < original_size:
            optimized_count += 1
        else:
            skipped_count += 1

        print()

    # Итоги
    print("=" * 60)
    print(f"✅ Обработано: {len(svg_files)} файлов")
    print(f"   Оптимизировано: {optimized_count}")
    print(f"   Пропущено (не уменьшились): {skipped_count}")
    print(f"   Исходный размер: {total_original:,} bytes ({total_original / 1024 / 1024:.1f} MB)")
    print(f"   Итоговый размер: {total_optimized:,} bytes ({total_optimized / 1024 / 1024:.1f} MB)")

    if total_original > 0:
        reduction = (1 - total_optimized / total_original) * 100
        saved = total_original - total_optimized
        print(f"   Сэкономлено: {saved:,} bytes ({saved / 1024 / 1024:.1f} MB, {reduction:.1f}%)")


if __name__ == "__main__":
    main()
