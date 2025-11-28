"""                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               scripts/auto_assign_design_images.py
Автоподбор main_image_path для design_images на основе структуры Seafile.

Структура на Seafile:
  /Конфигуратор/Графика/<model_dir>/<frame_dir>/<frame_color>/<insert_color>/<signature_folder>/<file.svg>

Запуск:
  python -m scripts.auto_assign_design_images          # записывает в БД
  python -m scripts.auto_assign_design_images --dry-run  # только выводит найденные пути
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Добавляем корень и app в sys.path
ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
for p in (ROOT, APP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.config import Settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import CoffeeMachine  # noqa: E402
from app.seafile_client import SeafileClient  # noqa: E402


BASE_DIR = "/Конфигуратор/Графика"


# === ВАРИАНТЫ "НЕТ" / "ОТСУТСТВУЕТ" (всё в нижнем регистре) ===
NO_VALUE_VARIANTS = {
    "нет", "net", "no", "none", "-", "",
    "отсутствует", "null", "н/д", "—", "–"
}

# === МАППИНГ КАРКАСОВ: БД -> Seafile (ключи в нижнем регистре) ===
FRAME_MAPPING = {
    "coffee zone mini": "mini",
    "coffee zone business": "business",
    "coffeezone mini": "mini",
    "coffeezone business": "business",
    "mini": "mini",
    "business": "business",
}

# Варианты написания "Без_каркаса" на Seafile (в нижнем регистре, без разделителей)
NO_FRAME_FOLDER_VARIANTS = {"безкаркаса", "noframe"}


_CYR_TO_LAT = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)


def norm_key(val: str) -> str:
    """Нормализует строку для сравнения (нижний регистр, без пробелов/разделителей)."""
    if not val:
        return ""
    s = (
        str(val)
        .lower()
        .translate(_CYR_TO_LAT)
        .replace("jetinno", "")
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )
    return s


def is_empty_value(val: Optional[str]) -> bool:
    """
    Проверяет, означает ли значение 'отсутствует' / 'нет'.
    Работает для каркаса, холодильника, терминала.
    Регистронезависимо.
    """
    if val is None:
        return True
    v = str(val).lower().strip()
    return v in NO_VALUE_VARIANTS


def is_no_frame_folder(name: str) -> bool:
    """Проверяет, является ли папка папкой 'без каркаса' (регистронезависимо)."""
    n = name.lower().replace("_", "").replace(" ", "").replace("-", "").strip()
    return n in NO_FRAME_FOLDER_VARIANTS


def match_frame(db_frame: str, folder_name: str) -> bool:
    """
    Сопоставляет название каркаса из БД с названием папки на Seafile.
    Регистронезависимо.

    Примеры:
      - "COFFEE ZONE MINI" -> "Mini" ✓
      - "coffee zone business" -> "Business" ✓
      - "Нет" / "НЕТ" / "нет" -> "Без_каркаса" ✓
    """
    if not folder_name:
        return False

    folder_norm = folder_name.lower().strip()
    folder_clean = folder_norm.replace("_", "").replace(" ", "").replace("-", "")

    # Случай "без каркаса"
    if is_empty_value(db_frame):
        return is_no_frame_folder(folder_name)

    # Если в БД есть каркас, папка "без_каркаса" не подходит
    if is_no_frame_folder(folder_name):
        return False

    db_norm = db_frame.lower().strip()

    # Пробуем через маппинг
    mapped = FRAME_MAPPING.get(db_norm)
    if mapped and folder_clean == mapped.replace("_", ""):
        return True

    # Пробуем частичное совпадение: "mini" в "coffee zone mini"
    if folder_norm in db_norm:
        return True

    # Пробуем нормализованное сравнение
    if norm_key(db_frame) == norm_key(folder_name):
        return True

    # Проверяем, содержит ли db_frame ключевое слово из folder_name
    folder_keywords = folder_norm.split()
    for kw in folder_keywords:
        if len(kw) > 2 and kw in db_norm:
            return True

    return False


def pick_entry(items: List[dict], target: str) -> Optional[str]:
    """Выбирает имя из items по нормализованному соответствию target (регистронезависимо)."""
    t_norm = norm_key(target)
    candidates = []

    if VERBOSE:
        print(f"  [pick_entry] Ищем '{target}' (norm: '{t_norm}')")

    for it in items:
        name = it.get("name") or ""
        if it.get("type") != "dir":
            continue
        name_norm = norm_key(name)

        # Точное совпадение
        if name_norm == t_norm:
            if VERBOSE:
                print(f"  [pick_entry] ✓ Точное совпадение: '{name}'")
            return name

        # Частичное совпадение (для случаев вроде "JL15_VIVA-ST-MW-PRO" vs "JL15_VIVA-ST-MW PRO")
        if t_norm in name_norm or name_norm in t_norm:
            candidates.append(name)
            if VERBOSE:
                print(f"  [pick_entry] ~ Частичное совпадение: '{name}' (norm: '{name_norm}')")

    # Если есть кандидаты с частичным совпадением, выбираем самый длинный
    if candidates:
        result = max(candidates, key=lambda x: len(norm_key(x)))
        if VERBOSE:
            print(f"  [pick_entry] → Выбран из кандидатов: '{result}'")
        return result

    if VERBOSE:
        print(f"  [pick_entry] ✗ Совпадений не найдено")
    return None


def pick_frame_entry(items: List[dict], db_frame: str) -> Optional[str]:
    """
    Выбирает папку каркаса из списка, сопоставляя с названием из БД.
    Регистронезависимо.
    """
    for it in items:
        if it.get("type") != "dir":
            continue
        name = it.get("name") or ""
        if match_frame(db_frame, name):
            return name
    return None


def parse_signature_folder(name: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Парсит подпапку вида '4_JL15_VIVA-ST-MW PRO+MC6D-B+vendista' -> (model, fridge, terminal)
    """
    if not name:
        return "", None, None
    parts = name.split("_", 1)
    payload = parts[1] if len(parts) > 1 else parts[0]
    tokens = payload.split("+")
    model = tokens[0].strip() if tokens else ""
    fridge = tokens[1].strip() if len(tokens) > 1 else None
    terminal = tokens[2].strip() if len(tokens) > 2 else None
    return model, fridge, terminal


def pick_file_for_insert(path: str, client: SeafileClient, machine: CoffeeMachine) -> Optional[Tuple[str, str]]:
    """
    Выбирает файл в папке insert_color с учётом сигнатуры (модель/холодильник/терминал).
    Все сравнения регистронезависимы.

    Returns:
        Tuple[str, str]: (file_path, gallery_folder_path) или None
    """
    try:
        items = client.list_directory(path)
    except Exception:
        return None

    # Если файлы лежат сразу в папке цвета вставки
    direct_files = [it for it in items if it.get("type") == "file"]
    if direct_files:
        f = direct_files[0]
        file_path = f.get("path") or f"{path.rstrip('/')}/{f.get('name')}"
        # В этом случае gallery_folder - это сама папка цвета вставки
        return (file_path, path)

    # Определяем, есть ли у машины холодильник/терминал (регистронезависимо)
    has_fridge = not is_empty_value(machine.refrigerator)
    has_terminal = not is_empty_value(machine.terminal)

    # Иначе ищем в подпапках с сигнатурой
    candidates: List[Tuple[int, str, str]] = []

    if VERBOSE:
        print(f"    [pick_file] Машина: model={machine.model}, fridge={machine.refrigerator if has_fridge else 'нет'}, terminal={machine.terminal if has_terminal else 'нет'}")

    for it in items:
        if it.get("type") != "dir":
            continue
        folder_name = it.get("name") or ""
        sig_model, sig_fridge, sig_terminal = parse_signature_folder(folder_name)

        if VERBOSE:
            print(f"    [pick_file] Проверяем папку: '{folder_name}' -> model={sig_model}, fridge={sig_fridge}, terminal={sig_terminal}")

        # Строгая проверка модели (регистронезависимо)
        if machine.model and norm_key(sig_model) != norm_key(machine.model):
            if VERBOSE:
                print(f"    [pick_file]   ✗ Модель не совпадает")
            continue

        # Холодильник
        if has_fridge:
            if sig_fridge and norm_key(sig_fridge) != norm_key(machine.refrigerator):
                if VERBOSE:
                    print(f"    [pick_file]   ✗ Холодильник не совпадает")
                continue
            if not sig_fridge:
                if VERBOSE:
                    print(f"    [pick_file]   ✗ Холодильник требуется, но не указан в папке")
                continue
        else:
            if sig_fridge:
                if VERBOSE:
                    print(f"    [pick_file]   ✗ Холодильник не требуется, но указан в папке")
                continue

        # Терминал
        if has_terminal:
            if sig_terminal and norm_key(sig_terminal) != norm_key(machine.terminal):
                if VERBOSE:
                    print(f"    [pick_file]   ✗ Терминал не совпадает")
                continue
        else:
            if sig_terminal:
                if VERBOSE:
                    print(f"    [pick_file]   ✗ Терминал не требуется, но указан в папке")
                continue

        # Подсчёт релевантности
        score = 0
        if machine.model and norm_key(sig_model) == norm_key(machine.model):
            score += 3
        if has_fridge and sig_fridge and norm_key(sig_fridge) == norm_key(machine.refrigerator):
            score += 2
        if has_terminal and sig_terminal and norm_key(sig_terminal) == norm_key(machine.terminal):
            score += 1

        inner_path = it.get("path") or f"{path.rstrip('/')}/{folder_name}"
        try:
            inner_items = client.list_directory(inner_path)
        except Exception:
            if VERBOSE:
                print(f"    [pick_file]   ✗ Не удалось открыть папку")
            continue
        file_item = next((inn for inn in inner_items if inn.get("type") == "file"), None)
        if not file_item:
            if VERBOSE:
                print(f"    [pick_file]   ✗ Нет файлов в папке")
            continue
        file_path = file_item.get("path") or f"{inner_path.rstrip('/')}/{file_item.get('name')}"
        # gallery_folder - это папка с сигнатурой (содержит все изображения для данной конфигурации)
        if VERBOSE:
            print(f"    [pick_file]   ✓ Подходит! Score={score}, file={file_item.get('name')}, gallery={inner_path}")
        candidates.append((score, file_path, inner_path))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return (candidates[0][1], candidates[0][2])
    return None


def build_design_images(machine: CoffeeMachine, client: SeafileClient) -> Dict[str, Dict[str, Dict[str, str]]]:
    """Возвращает найденные design_images для машины, или пустой словарь."""
    try:
        model_entries = client.list_directory(BASE_DIR)
    except Exception as exc:
        print(f"[{machine.id}] Не удалось открыть {BASE_DIR}: {exc}")
        return {}

    model_dir = pick_entry(model_entries, machine.model or machine.name)
    if not model_dir:
        names = [it.get("name") for it in model_entries if it.get("type") == "dir"]
        print(
            f"[{machine.id}] Не найден каталог модели для '{machine.model or machine.name}', доступно: {names}"
        )
        return {}

    model_path = f"{BASE_DIR}/{model_dir}"
    try:
        frame_entries = client.list_directory(model_path)
    except Exception as exc:
        print(f"[{machine.id}] Не удалось открыть {model_path}: {exc}")
        return {}

    # Определяем целевой каркас (или "без каркаса")
    db_frame = machine.frame or ""

    # Ищем соответствующую папку каркаса
    frame_dir = pick_frame_entry(frame_entries, db_frame)

    if not frame_dir:
        available = [it.get("name") for it in frame_entries if it.get("type") == "dir"]
        frame_desc = f"'{db_frame}'" if not is_empty_value(db_frame) else "'Без каркаса'"
        print(f"[{machine.id}] Не найден каркас {frame_desc}, доступно: {available}")
        return {}

    print(f"[{machine.id}] Сопоставлен каркас: '{db_frame or 'Нет'}' -> '{frame_dir}'")

    result: Dict[str, Dict[str, Dict[str, str]]] = {}

    frame_path = f"{model_path}/{frame_dir}"
    try:
        color_entries = client.list_directory(frame_path)
    except Exception:
        print(f"[{machine.id}] Не удалось открыть {frame_path}")
        return {}

    for color_entry in color_entries:
        if color_entry.get("type") != "dir":
            continue
        frame_color = color_entry.get("name")
        color_path = color_entry.get("path") or f"{frame_path}/{frame_color}"
        try:
            insert_entries = client.list_directory(color_path)
        except Exception:
            print(f"[{machine.id}] Не удалось открыть {color_path}")
            continue

        for insert_entry in insert_entries:
            if insert_entry.get("type") != "dir":
                continue
            insert_color = insert_entry.get("name")
            insert_path = insert_entry.get("path") or f"{color_path}/{insert_color}"
            file_result = pick_file_for_insert(insert_path, client, machine)
            if not file_result:
                print(f"[{machine.id}] Нет подходящего файла в {insert_path}")
                continue
            file_path, gallery_folder = file_result
            result.setdefault(frame_color, {})[insert_color] = {
                "main_image_path": file_path,
                "main_image": file_path,
                "gallery_folder": gallery_folder,
            }

    if not result:
        print(f"[{machine.id}] Не удалось найти design_images в {frame_path}")
    return result


# Глобальная переменная для verbose режима
VERBOSE = False


def main() -> None:
    global VERBOSE

    parser = argparse.ArgumentParser(description="Автоподбор main_image_path для design_images из Seafile")
    parser.add_argument("--dry-run", action="store_true", help="Только вывод, без записи в БД")
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    parser.add_argument("--with-frame", action="store_true", help="Только записи С каркасом")
    parser.add_argument("--without-frame", action="store_true", help="Только записи БЕЗ каркаса")
    args = parser.parse_args()

    VERBOSE = args.verbose

    settings = Settings()
    client = SeafileClient(settings.seafile_server, settings.seafile_repo_id, settings.seafile_token)
    db = SessionLocal()

    machines: List[CoffeeMachine] = db.query(CoffeeMachine).all()
    updated = 0
    skipped = 0

    for m in machines:
        has_frame = not is_empty_value(m.frame)

        # Фильтрация по флагам
        if args.with_frame and not has_frame:
            skipped += 1
            continue
        if args.without_frame and has_frame:
            skipped += 1
            continue

        design_images = build_design_images(m, client)
        if not design_images:
            continue

        frame_info = m.frame if has_frame else "Без каркаса"

        if args.dry_run:
            print(f"[DRY] id={m.id} model={m.model or m.name} frame={frame_info}")
            for fc, inserts in design_images.items():
                for ic, cfg in inserts.items():
                    print(f"   {fc}/{ic}:")
                    print(f"      main_image_path: {cfg.get('main_image_path')}")
                    print(f"      gallery_folder:  {cfg.get('gallery_folder')}")
            updated += 1
            continue

        # Сливаем с существующими
        existing = m.design_images if isinstance(m.design_images, dict) else {}
        merged = existing.copy()
        for fc, inserts in design_images.items():
            merged.setdefault(fc, {})
            merged[fc].update(inserts)
        m.design_images = merged
        db.add(m)
        updated += 1
        total_combos = sum(len(inserts) for inserts in design_images.values())
        print(f"[OK] id={m.id} model={m.model or m.name} frame={frame_info}: обновлены design_images ({len(design_images)} цветов каркаса, {total_combos} комбинаций)")

    if not args.dry_run:
        db.commit()
        print(f"\nГотово: обновлено {updated} записей, пропущено {skipped}")
    else:
        print(f"\nDRY RUN: найдено {updated} записей (без записи в БД)")

    db.close()


if __name__ == "__main__":
    main()



