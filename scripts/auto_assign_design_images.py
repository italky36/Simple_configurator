"""                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               scripts/auto_assign_design_images.py
Автоподбор main_image_path для design_images на основе структуры Seafile.

Структура на Seafile:
  /Конфигуратор/Графика/<model_dir>/<frame_dir>/<frame_color>/<insert_color>/<signature_folder>/<file.svg>

Запуск:
  python -m scripts.auto_assign_design_images          # записывает в БД
  python -m scripts.auto_assign_design_images --dry-run  # только выводит найденные пути
"""

import argparse
import re
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
from app.services import media_cache  # noqa: E402


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


_CYR_TO_LAT = str.maketrans({
    "а": "a",   # а
    "б": "b",   # б
    "в": "v",   # в
    "г": "g",   # г
    "д": "d",   # д
    "е": "e",   # е
    "ё": "e",   # ё
    "ж": "zh",  # ж
    "з": "z",   # з
    "и": "i",   # и
    "й": "i",   # й
    "к": "k",   # к
    "л": "l",   # л
    "м": "m",   # м
    "н": "n",   # н
    "о": "o",   # о
    "п": "p",   # п
    "р": "r",   # р
    "с": "s",   # с
    "т": "t",   # т
    "у": "u",   # у
    "ф": "f",   # ф
    "х": "h",   # х
    "ц": "ts",  # ц
    "ч": "ch",  # ч
    "ш": "sh",  # ш
    "щ": "shch",# щ
    "ъ": "",    # ъ
    "ы": "y",   # ы
    "ь": "",    # ь
    "э": "e",   # э
    "ю": "yu",  # ю
    "я": "ya",  # я
    "є": "e",   # є
    "і": "i",   # і
    "ї": "i",   # ї
    "ґ": "g",   # ґ
})


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


def fuzzy_match(db_value: str, seafile_value: str) -> bool:
    """
    Гибкое сопоставление названий с учетом версий и вариаций написания.
    Например: 'Vendista v2.5' совпадает с 'vendista'
              'MC16DAST' совпадает с 'MC16DAST'
    """
    if not db_value or not seafile_value:
        return False

    db_norm = norm_key(db_value)
    sf_norm = norm_key(seafile_value)

    # Точное совпадение
    if db_norm == sf_norm:
        return True

    # Убираем версии из БД (v2.5, v3.0, etc.) для сравнения
    db_no_version = re.sub(r'v\d+(\.\d+)?', '', db_norm)

    # Проверяем совпадение без версии
    if db_no_version == sf_norm:
        return True

    # Частичное совпадение (seafile содержится в db или наоборот)
    if len(sf_norm) >= 3 and (sf_norm in db_norm or db_norm in sf_norm):
        return True

    return False


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
    # Также нормализуем без транслитерации (для случая с кириллицей в названии)
    t_simple = target.lower().replace(" ", "").replace("_", "").replace("-", "")
    candidates = []

    if VERBOSE:
        print(f"  [pick_entry] Ищем '{target}' (norm: '{t_norm}')")

    for it in items:
        name = it.get("name") or ""
        if it.get("type") != "dir":
            continue
        name_norm = norm_key(name)
        name_simple = name.lower().replace(" ", "").replace("_", "").replace("-", "")

        # Точное совпадение после нормализации
        if name_norm == t_norm:
            if VERBOSE:
                print(f"  [pick_entry] ✓ Точное совпадение: '{name}'")
            return name

        # Точное совпадение без транслитерации (для кириллицы)
        if name_simple == t_simple:
            if VERBOSE:
                print(f"  [pick_entry] ✓ Совпадение (кириллица): '{name}'")
            return name

        # Частичное совпадение (для случаев вроде "JL15_VIVA-ST-MW-PRO" vs "JL15_VIVA-ST-MW PRO")
        if t_norm in name_norm or name_norm in t_norm:
            candidates.append((name, 2))  # приоритет 2
        elif t_simple in name_simple or name_simple in t_simple:
            candidates.append((name, 1))  # приоритет 1 (кириллица)
            if VERBOSE:
                print(f"  [pick_entry] ~ Частичное совпадение (кириллица): '{name}' (simple: '{name_simple}')")

    # Если есть кандидаты с частичным совпадением, выбираем с наивысшим приоритетом
    if candidates:
        # Сортируем по приоритету (выше лучше), затем по длине
        candidates.sort(key=lambda x: (x[1], len(x[0])), reverse=True)
        result = candidates[0][0]
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
            if sig_fridge and not fuzzy_match(machine.refrigerator, sig_fridge):
                if VERBOSE:
                    print(f"    [pick_file]   ✗ Холодильник не совпадает (БД: {machine.refrigerator}, Seafile: {sig_fridge})")
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
            if sig_terminal and not fuzzy_match(machine.terminal, sig_terminal):
                if VERBOSE:
                    print(f"    [pick_file]   ✗ Терминал не совпадает (БД: {machine.terminal}, Seafile: {sig_terminal})")
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
        if has_fridge and sig_fridge and fuzzy_match(machine.refrigerator, sig_fridge):
            score += 2
        if has_terminal and sig_terminal and fuzzy_match(machine.terminal, sig_terminal):
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

    # Проверяем, что у машины указан каркас и цвет каркаса
    if is_empty_value(machine.frame):
        if VERBOSE:
            print(f"[{machine.id}] Пропускаем: каркас не указан")
        return {}

    if is_empty_value(machine.frame_color):
        if VERBOSE:
            print(f"[{machine.id}] Пропускаем: цвет каркаса не указан")
        return {}

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

    # Обрабатываем только цвет каркаса, указанный в БД
    target_frame_color = machine.frame_color
    print(f"[{machine.id}] Ищем цвет каркаса: '{target_frame_color}'")

    for color_entry in color_entries:
        if color_entry.get("type") != "dir":
            continue
        frame_color = color_entry.get("name")

        # Обрабатываем ТОЛЬКО тот цвет каркаса, который указан в БД
        if not fuzzy_match(target_frame_color, frame_color):
            if VERBOSE:
                print(f"  [build] Пропускаем цвет каркаса '{frame_color}' (нужен '{target_frame_color}')")
            continue

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

            if VERBOSE:
                print(f"  [build] Обрабатываем {frame_color}/{insert_color}")

            file_result = pick_file_for_insert(insert_path, client, machine)
            if not file_result:
                print(f"[{machine.id}] ⚠️  Нет подходящего файла в {insert_path}")
                continue
            file_path, gallery_folder = file_result
            # Преобразуем русские названия цветов в английские ключи
            # Это решает проблемы с кодировкой (ё/е) и упрощает работу фронтенда
            def normalize_color_key(color_name: str) -> str:
                """Преобразует русское название цвета в английский ключ."""
                normalized = color_name.lower().replace('ё', 'е')  # Нормализуем ё→е для сопоставления
                # Маппинг русских названий на английские ключи
                # FRAME_COLORS: white, black
                # INSERT_COLORS: yellow, green, red, gray, blue, purple
                color_map = {
                    "белый": "white",
                    "черный": "black",
                    "желтый": "yellow",
                    "зеленый": "green",
                    "красный": "red",
                    "серый": "gray",
                    "синий": "blue",
                    "фиолетовый": "purple",
                }
                return color_map.get(normalized, normalized)

            frame_color_key = normalize_color_key(frame_color)
            insert_color_key = normalize_color_key(insert_color)
            result.setdefault(frame_color_key, {})[insert_color_key] = {
                "main_image_path": file_path,
                "main_image": file_path,
                "gallery_folder": gallery_folder,
            }
            print(f"[{machine.id}] ✓ {frame_color}/{insert_color} -> {file_path[:80]}...")

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
    parser.add_argument("--no-cache", action="store_true", help="Не кешировать изображения на сервер")
    parser.add_argument("--machine-id", type=int, help="Обработать только конкретную машину по ID")
    args = parser.parse_args()

    VERBOSE = args.verbose

    settings = Settings()
    client = SeafileClient(settings.seafile_server, settings.seafile_repo_id, settings.seafile_token)
    db = SessionLocal()

    # Если указан --machine-id, обрабатываем только эту машину
    if args.machine_id:
        machines: List[CoffeeMachine] = db.query(CoffeeMachine).filter(CoffeeMachine.id == args.machine_id).all()
        if not machines:
            print(f"❌ Машина с ID {args.machine_id} не найдена в базе данных")
            return
        print(f"🎯 Обработка только машины ID {args.machine_id}")
    else:
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

        # Кешируем изображения на сервер
        if not args.no_cache:
            print(f"[CACHE] Кеширование изображений для машины {m.id}...")
            media_cache.cache_machine_media(m, client)
            print(f"[CACHE] Готово для машины {m.id}")

    if not args.dry_run:
        db.commit()
        print(f"\nГотово: обновлено {updated} записей, пропущено {skipped}")
    else:
        print(f"\nDRY RUN: найдено {updated} записей (без записи в БД)")

    db.close()


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # Игнорируем BrokenPipeError при использовании с pipe (например, | head)
        import sys
        sys.stderr.close()
        sys.exit(0)



