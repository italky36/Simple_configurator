import shutil
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse
import subprocess

import requests

# Все файлы кеша складываются в /app/static/cache/machines/{id}/...
CACHE_ROOT = Path("app/static/cache/machines")
STATIC_PREFIX = "/static/cache/machines"

# Минимальная транслитерация русского -> латиница для имён файлов
_RU_MAP = str.maketrans(
    {
        "\u0430": "a",
        "\u0431": "b",
        "\u0432": "v",
        "\u0433": "g",
        "\u0434": "d",
        "\u0435": "e",
        "\u0451": "e",
        "\u0436": "zh",
        "\u0437": "z",
        "\u0438": "i",
        "\u0439": "i",
        "\u043a": "k",
        "\u043b": "l",
        "\u043c": "m",
        "\u043d": "n",
        "\u043e": "o",
        "\u043f": "p",
        "\u0440": "r",
        "\u0441": "s",
        "\u0442": "t",
        "\u0443": "u",
        "\u0444": "f",
        "\u0445": "h",
        "\u0446": "c",
        "\u0447": "ch",
        "\u0448": "sh",
        "\u0449": "shch",
        "\u044a": "",
        "\u044b": "y",
        "\u044c": "",
        "\u044d": "e",
        "\u044e": "yu",
        "\u044f": "ya",
    }
)


def _guess_ext(url: str, fallback: str = ".jpg") -> str:
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix
    if ext and len(ext) <= 5:
        return ext
    return fallback


def _safe_name(name: str) -> str:
    return Path(name).name


def _slugify(value: str) -> str:
    """
    Транслитерация + очистка: латиница/цифры/подчёркивания, остальное -> "_".
    """
    if not value:
        return ""
    translit = value.lower().translate(_RU_MAP)
    cleaned = []
    prev_us = False
    for ch in translit:
        if ch.isalnum():
            cleaned.append(ch)
            prev_us = False
        else:
            if not prev_us:
                cleaned.append("_")
            prev_us = True
    result = "".join(cleaned).strip("_")
    return result or "item"


def clear_machine_cache(machine_id: int) -> None:
    shutil.rmtree(CACHE_ROOT / str(machine_id), ignore_errors=True)


def _optimize_svg(path: Path) -> None:
    """Оптимизирует SVG файл с помощью scour для уменьшения размера."""
    try:
        # Проверяем что установлен scour
        result = subprocess.run(
            ["scour", "--version"],
            capture_output=True,
            timeout=5
        )
        if result.returncode != 0:
            print(f"⚠️  scour not installed, skipping SVG optimization")
            return

        # Оптимизируем SVG
        temp_path = path.with_suffix('.svg.tmp')
        result = subprocess.run(
            [
                "scour",
                "--enable-id-stripping",
                "--enable-comment-stripping",
                "--shorten-ids",
                "--indent=none",
                "-i", str(path),
                "-o", str(temp_path)
            ],
            capture_output=True,
            timeout=30
        )

        if result.returncode == 0 and temp_path.exists():
            # Проверяем что оптимизированный файл меньше
            original_size = path.stat().st_size
            optimized_size = temp_path.stat().st_size

            if optimized_size < original_size:
                temp_path.replace(path)
                reduction = (1 - optimized_size / original_size) * 100
                print(f"  ✓ SVG optimized: {original_size:,} → {optimized_size:,} bytes ({reduction:.1f}% reduction)")
            else:
                temp_path.unlink()
                print(f"  ℹ️  Optimization didn't reduce size, keeping original")
        else:
            if temp_path.exists():
                temp_path.unlink()
            print(f"  ⚠️  SVG optimization failed: {result.stderr.decode()[:100]}")
    except FileNotFoundError:
        print(f"  ⚠️  scour not found, skipping SVG optimization")
    except Exception as e:
        print(f"  ⚠️  SVG optimization error: {e}")


def _download_to(path: Path, url: str) -> Optional[Path]:
    try:
        resp = requests.get(url, stream=True, timeout=20, verify=False)
        if resp.status_code in (401, 403):
            return None
        resp.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Оптимизируем SVG файлы
        if path.suffix.lower() == '.svg':
            _optimize_svg(path)

        return path
    except Exception:
        return None


def cache_main_image(machine_id: int, url: str) -> Optional[str]:
    if not url:
        return None
    ext = _guess_ext(url)
    dest = CACHE_ROOT / str(machine_id) / f"main{ext}"
    path = _download_to(dest, url)
    if not path:
        return None
    return f"{STATIC_PREFIX}/{machine_id}/{path.name}"


def cache_design_image(machine_id: int, frame_color: str, insert_color: str, url: str) -> Optional[str]:
    """
    Скачивает main_image для комбинации frame/insert и кладёт под ASCII-имя.
    """
    if not url:
        return None
    safe_frame = _slugify(frame_color.replace("/", "_").replace("\\", "_"))
    safe_insert = _slugify(insert_color.replace("/", "_").replace("\\", "_"))
    filename = f"design_{safe_frame}_{safe_insert}"
    ext = _guess_ext(url)
    dest = CACHE_ROOT / str(machine_id) / f"{filename}{ext}"
    path = _download_to(dest, url)
    if not path:
        return None
    return f"{STATIC_PREFIX}/{machine_id}/{path.name}"


def cache_gallery_files(machine_id: int, files: Iterable[Tuple[str, str]]) -> List[str]:
    """files: iterable of (name, url)"""
    cached: List[str] = []
    for name, url in files:
        if not url:
            continue
        fname = _safe_name(name)
        ext = Path(fname).suffix or _guess_ext(url, ".jpg")
        slug_base = _slugify(Path(fname).stem)
        dest_name = f"{slug_base}{ext}"
        dest = CACHE_ROOT / str(machine_id) / "gallery" / dest_name
        path = _download_to(dest, url)
        if path:
            cached.append(f"{STATIC_PREFIX}/{machine_id}/gallery/{path.name}")
    return cached


def get_cached_main(machine_id: int) -> Optional[str]:
    folder = CACHE_ROOT / str(machine_id)
    if not folder.exists():
        return None
    for file in folder.glob("main.*"):
        return f"{STATIC_PREFIX}/{machine_id}/{file.name}"
    return None


def get_cached_design_image(machine_id: int, frame_color: str, insert_color: str) -> Optional[str]:
    """
    Возвращает закешированное изображение для комбинации frame/insert (ASCII-имя).
    """
    folder = CACHE_ROOT / str(machine_id)
    if not folder.exists():
        return None
    safe_frame = _slugify(frame_color.replace("/", "_").replace("\\", "_"))
    safe_insert = _slugify(insert_color.replace("/", "_").replace("\\", "_"))
    pattern = f"design_{safe_frame}_{safe_insert}.*"
    for file in folder.glob(pattern):
        return f"{STATIC_PREFIX}/{machine_id}/{file.name}"
    return None


def get_cached_gallery(machine_id: int) -> List[str]:
    folder = CACHE_ROOT / str(machine_id) / "gallery"
    if not folder.exists():
        return []
    return [f"{STATIC_PREFIX}/{machine_id}/gallery/{p.name}" for p in sorted(folder.iterdir()) if p.is_file()]


def cache_machine_media(machine, seafile_client) -> None:
    """Полный прогрев кэша: main + gallery + design_images."""
    clear_machine_cache(machine.id)

    main_url = None
    if getattr(machine, "main_image_path", None):
        try:
            main_url = seafile_client.get_file_download_link(machine.main_image_path)
        except Exception:
            main_url = None
    elif machine.main_image:
        main_url = machine.main_image

    if main_url:
        cache_main_image(machine.id, main_url)

    if hasattr(machine, "design_images") and machine.design_images:
        print(f"== Caching design_images for machine {machine.id}")
        for frame_color, insert_colors in machine.design_images.items():
            for insert_color, config in insert_colors.items():
                img_path = config.get("main_image_path") or config.get("main_image")
                if not img_path:
                    continue
                try:
                    img_url = seafile_client.get_file_download_link(img_path)
                    cached = cache_design_image(machine.id, frame_color, insert_color, img_url)
                    if cached:
                        print(f"  OK Cached {frame_color}/{insert_color}: {cached}")
                except Exception as e:
                    print(f"  WARN Failed to cache {frame_color}/{insert_color}: {e}")

    if not machine.gallery_folder:
        return

    folder_path = machine.gallery_folder
    if not folder_path.startswith("/"):
        folder_path = "/" + folder_path

    try:
        items = seafile_client.list_directory(folder_path)
    except Exception:
        return

    files: List[Tuple[str, str]] = []
    for item in items:
        if item.get("type") != "file":
            continue
        file_path = item.get("path") or f"{folder_path.rstrip('/')}/{item.get('name')}"
        try:
            link = seafile_client.get_file_download_link(file_path)
        except Exception:
            continue
        files.append((item.get("name") or Path(file_path).name, link))

    cache_gallery_files(machine.id, files)
