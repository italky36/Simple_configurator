"""
Автоподбор main_image_path для машин БЕЗ каркаса.

Структура на Seafile (пример):
  /Конфигуратор/Графика/<model_dir>/<frame_dir>/Без_каркаса/<signature_folder>/<file.svg>
    где signature_folder = "<N>_<MODEL>[+FRIDGE][+TERMINAL]"

Использование:
  python -m scripts.auto_assign_no_frame_images          # записывает в БД
  python -m scripts.auto_assign_no_frame_images --dry-run  # только выводит найденные пути
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy.orm.attributes import flag_modified

# Приводим sys.path в то же состояние, что и базовый скрипт
ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
for p in (ROOT, APP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Используем функции из базового скрипта для смачивания моделей/сигнатур
from scripts import auto_assign_design_images as base  # noqa: E402

Settings = base.Settings
SessionLocal = base.SessionLocal
CoffeeMachine = base.CoffeeMachine
SeafileClient = base.SeafileClient
media_cache = base.media_cache

BASE_DIR = base.BASE_DIR
NO_FRAME_FOLDER_VARIANTS = base.NO_FRAME_FOLDER_VARIANTS
norm_key = base.norm_key
pick_entry = base.pick_entry
parse_signature_folder = base.parse_signature_folder
fuzzy_match = base.fuzzy_match
is_empty_value = base.is_empty_value


def is_no_frame_folder(name: str) -> bool:
    n = name.lower().replace("_", "").replace(" ", "").replace("-", "").strip()
    return n in NO_FRAME_FOLDER_VARIANTS


def pick_file_in_no_frame(path: str, client: SeafileClient, machine: CoffeeMachine) -> Optional[Tuple[str, str]]:
    """
    Подбирает файл внутри папки Без_каркаса, используя ту же сигнатуру, что и base.pick_file_for_insert.
    Возвращает (file_path, gallery_folder) или None.
    """
    try:
        items = client.list_directory(path)
    except Exception:
        return None

    # Если файл лежит прямо в Без_каркаса
    direct_files = [it for it in items if it.get("type") == "file"]
    if direct_files:
        f = direct_files[0]
        file_path = f.get("path") or f"{path.rstrip('/')}/{f.get('name')}"
        return (file_path, path)

    has_fridge = not is_empty_value(machine.refrigerator)
    has_terminal = not is_empty_value(machine.terminal)
    candidates: List[Tuple[int, str, str]] = []

    for it in items:
        if it.get("type") != "dir":
            continue
        folder_name = it.get("name") or ""
        sig_model, sig_fridge, sig_terminal = parse_signature_folder(folder_name)

        # Модель должна совпасть
        if machine.model and norm_key(sig_model) != norm_key(machine.model):
            continue

        # Холодильник
        if has_fridge:
            if sig_fridge and not fuzzy_match(machine.refrigerator, sig_fridge):
                continue
            if not sig_fridge:
                continue
        else:
            if sig_fridge:
                continue

        # Терминал
        if has_terminal:
            if sig_terminal and not fuzzy_match(machine.terminal, sig_terminal):
                continue
        else:
            if sig_terminal:
                continue

        score = 0
        if machine.model and norm_key(sig_model) == norm_key(machine.model):
            score += 3
        if has_fridge and sig_fridge and fuzzy_match(machine.refrigerator, sig_fridge):
            score += 2
        if has_terminal and sig_terminal and fuzzy_match(machine.terminal, sig_terminal):
            score += 1

        inner_path = it.get("path") or f"{path.rstrip('/')}/{folder_name}"
        try:
            inner_items = client.list_directory(inner_path)
        except Exception:
            continue
        file_item = next((inn for inn in inner_items if inn.get("type") == "file"), None)
        if not file_item:
            continue
        file_path = file_item.get("path") or f"{inner_path.rstrip('/')}/{file_item.get('name')}"
        candidates.append((score, file_path, inner_path))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return (candidates[0][1], candidates[0][2])
    return None


def build_no_frame_image(machine: CoffeeMachine, client: SeafileClient) -> Optional[Tuple[str, str]]:
    """
    Ищет подходящий файл для машины без каркаса.
    Возвращает (main_image_path, gallery_folder) или None.
    """
    try:
        model_entries = client.list_directory(BASE_DIR)
    except Exception as exc:
        print(f"[{machine.id}] Не удалось открыть {BASE_DIR}: {exc}")
        return None

    model_dir = pick_entry(model_entries, machine.model or machine.name)
    if not model_dir:
        names = [it.get("name") for it in model_entries if it.get("type") == "dir"]
        print(f"[{machine.id}] Не найден каталог модели для '{machine.model or machine.name}', доступно: {names}")
        return None

    model_path = f"{BASE_DIR}/{model_dir}"
    try:
        frame_entries = client.list_directory(model_path)
    except Exception as exc:
        print(f"[{machine.id}] Не удалось открыть {model_path}: {exc}")
        return None

    # Приоритет — сначала Business, затем Mini, затем остальные
    def frame_priority(name: str) -> int:
        n = norm_key(name)
        if "business" in n:
            return 2
        if "mini" in n:
            return 1
        return 0

    frame_dirs = [fe for fe in frame_entries if fe.get("type") == "dir"]
    frame_dirs.sort(key=lambda fe: frame_priority(fe.get("name") or ""), reverse=True)

    for fe in frame_dirs:
        frame_name = fe.get("name") or ""
        frame_path = fe.get("path") or f"{model_path}/{frame_name}"
        try:
            inner = client.list_directory(frame_path)
        except Exception:
            continue
        no_frame_dir = next(
            (it for it in inner if it.get("type") == "dir" and is_no_frame_folder(it.get("name") or "")),
            None,
        )
        if not no_frame_dir:
            continue

        nf_name = no_frame_dir.get("name") or ""
        nf_path = no_frame_dir.get("path") or f"{frame_path}/{nf_name}"

        file_result = pick_file_in_no_frame(nf_path, client, machine)
        if file_result:
            return file_result

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Автоподбор main_image_path для машин без каркаса из Seafile")
    parser.add_argument("--dry-run", action="store_true", help="Только вывод, без записи в БД")
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    parser.add_argument("--machine-id", type=int, help="Обработать только конкретную машину по ID")
    parser.add_argument("--no-cache", action="store_true", help="Не кешировать изображения на сервер")
    parser.add_argument("--no-gallery-cache", action="store_true", help="Не кешировать и не создавать папку gallery")
    args = parser.parse_args()

    base.VERBOSE = args.verbose

    settings = Settings()
    client = SeafileClient(settings.seafile_server, settings.seafile_repo_id, settings.seafile_token)
    db = SessionLocal()

    # Забираем из БД и фильтруем по "нет" уже в Python (учитываем все варианты написания)
    query = db.query(CoffeeMachine)
    if args.machine_id:
        query = query.filter(CoffeeMachine.id == args.machine_id)
    candidates: List[CoffeeMachine] = query.all()
    machines: List[CoffeeMachine] = [m for m in candidates if is_empty_value(m.frame)]

    if not machines:
        print("Нет подходящих машин (без каркаса) для обработки")
        return

    updated = 0
    for m in machines:
        result = build_no_frame_image(m, client)
        if not result:
            continue
        file_path, gallery_folder = result

        if args.dry_run:
            print(f"[DRY] id={m.id} model={m.model or m.name} -> {file_path[:80]}...")
            updated += 1
            continue

        m.main_image_path = file_path
        m.main_image = file_path
        m.gallery_folder = gallery_folder
        # На всякий случай помечаем design_images как изменённые (могут быть пустыми)
        flag_modified(m, "design_images")
        db.add(m)
        updated += 1

        if args.verbose:
            print(f"[OK] id={m.id} model={m.model or m.name}: main_image_path={file_path}, gallery={gallery_folder}")

        if not args.no_cache and not args.no_gallery_cache:
            try:
                print(f"[CACHE] Кеширование изображений для машины {m.id}...")
                media_cache.cache_machine_media(m, client)
            except Exception as e:
                print(f"[CACHE] ⚠️  Не удалось кешировать для {m.id}: {e}")
        elif args.no_gallery_cache and base.VERBOSE:
            print(f"[CACHE] Пропущено кеширование gallery для машины {m.id} (флаг --no-gallery-cache)")

    if not args.dry_run:
        db.commit()
        print(f"\nГотово: обновлено {updated} записей")
    else:
        print(f"\nDRY RUN: найдено {updated} записей (без записи в БД)")

    db.close()


if __name__ == "__main__":
    main()
