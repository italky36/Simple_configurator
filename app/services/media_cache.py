import shutil
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests

# Простое файловое кеширование картинок из Seafile и других URL.
# Все файлы складываются в /app/static/cache/machines/{id}/...
CACHE_ROOT = Path("app/static/cache/machines")
STATIC_PREFIX = "/static/cache/machines"


def _guess_ext(url: str, fallback: str = ".jpg") -> str:
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix
    if ext and len(ext) <= 5:
        return ext
    return fallback


def _safe_name(name: str) -> str:
    # Убираем подкаталоги из имени
    return Path(name).name


def clear_machine_cache(machine_id: int) -> None:
    shutil.rmtree(CACHE_ROOT / str(machine_id), ignore_errors=True)


def _download_to(path: Path, url: str) -> Optional[Path]:
    try:
        resp = requests.get(url, stream=True, timeout=20)
        if resp.status_code == 403 or resp.status_code == 401:
            return None
        resp.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
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


def cache_gallery_files(machine_id: int, files: Iterable[Tuple[str, str]]) -> List[str]:
    """files: iterable of (name, url)"""
    cached: List[str] = []
    for name, url in files:
        if not url:
            continue
        fname = _safe_name(name)
        ext = Path(fname).suffix or _guess_ext(url, ".jpg")
        dest_name = fname if Path(fname).suffix else f"{fname}{ext}"
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


def get_cached_gallery(machine_id: int) -> List[str]:
    folder = CACHE_ROOT / str(machine_id) / "gallery"
    if not folder.exists():
        return []
    return [f"{STATIC_PREFIX}/{machine_id}/gallery/{p.name}" for p in sorted(folder.iterdir()) if p.is_file()]


def cache_machine_media(machine, seafile_client) -> None:
    """Полное обновление кеша для записи: main + gallery."""
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
