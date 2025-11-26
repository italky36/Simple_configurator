from typing import Any, Dict, List, Optional
import requests
import json
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException

from .. import crud
from ..config import Settings
from ..database import get_db
from ..seafile_client import SeafileClient
from ..ozon_client import OzonClient
from ..services import media_cache
from ..models import Lead

router = APIRouter(prefix="/api")
settings = Settings()
seafile_client = SeafileClient(settings.seafile_server, settings.seafile_repo_id, settings.seafile_token)
ozon_client = OzonClient(settings.ozon_client_id or "", settings.ozon_api_key or "") if settings.ozon_client_id and settings.ozon_api_key else None


def machine_to_dict(
    machine,
    include_gallery: bool = False,
    include_ozon_price: bool = False,
    frame_color: Optional[str] = None,
    insert_color: Optional[str] = None,
) -> Dict[str, Any]:
    # Выбор изображения на основе design_images, если указаны frame_color и insert_color
    main_source_url = None
    main_source_path = None
    gallery_folder_override = None

    if frame_color and insert_color and machine.design_images:
        design_config = machine.design_images.get(frame_color, {}).get(insert_color, {})
        if design_config:
            main_source_path = design_config.get("main_image_path") or design_config.get("main_image")
            gallery_folder_override = design_config.get("gallery_folder")

    # Если не нашли в design_images, используем стандартные поля
    if not main_source_path:
        main_source_path = machine.main_image_path or machine.main_image

    # Кеширование работает только для обычных main_image (без цветов)
    # Для design_images возвращаем прямые Seafile ссылки без кеширования
    cached_main = None
    if not frame_color and not insert_color:
        # Обычная машина без выбора цветов - используем кеш
        cached_main = media_cache.get_cached_main(machine.id)

    if main_source_path:
        try:
            main_source_url = seafile_client.get_file_download_link(main_source_path)
        except Exception:
            main_source_url = main_source_path

    # Кешируем только обычные main_image
    if not cached_main and main_source_url and not frame_color and not insert_color:
        cached_main = media_cache.cache_main_image(machine.id, main_source_url)

    # Используем переопределенную gallery_folder если есть
    effective_gallery_folder = gallery_folder_override or machine.gallery_folder

    # Обработка design_images: преобразуем пути Seafile в прямые ссылки И кешируем
    processed_design_images = None
    if hasattr(machine, 'design_images') and machine.design_images:
        print(f"🎨 Processing design_images for machine {machine.id} ({machine.name})")
        processed_design_images = {}
        for frame_col, insert_colors in machine.design_images.items():
            processed_design_images[frame_col] = {}
            for insert_col, config in insert_colors.items():
                processed_config = {}
                # Получаем ссылку на main_image
                if config.get("main_image_path") or config.get("main_image"):
                    img_path = config.get("main_image_path") or config.get("main_image")

                    # Проверяем кеш
                    cached_design = media_cache.get_cached_design_image(machine.id, frame_col, insert_col)
                    if cached_design:
                        processed_config["main_image"] = cached_design
                        processed_config["main_image_path"] = img_path
                        print(f"  ✓ {frame_col}/{insert_col}: Using cached {cached_design}")
                    else:
                        # Кеша нет, получаем Seafile ссылку и кешируем
                        try:
                            img_url = seafile_client.get_file_download_link(img_path)
                            # Кешируем на диск
                            cached_design = media_cache.cache_design_image(machine.id, frame_col, insert_col, img_url)
                            if cached_design:
                                processed_config["main_image"] = cached_design
                                print(f"  ✓ {frame_col}/{insert_col}: Cached {img_path[:50]}... -> {cached_design}")
                            else:
                                # Не удалось закешировать, используем прямую ссылку
                                processed_config["main_image"] = img_url
                                print(f"  ⚠️  {frame_col}/{insert_col}: Failed to cache, using direct link")
                            processed_config["main_image_path"] = img_path
                        except Exception as e:
                            print(f"  ❌ Failed to get Seafile link for {frame_col}/{insert_col}: {img_path} - {e}")
                            # Если не удалось получить ссылку, используем путь как есть
                            processed_config["main_image"] = img_path
                            processed_config["main_image_path"] = img_path

                # Копируем gallery_folder если есть
                if config.get("gallery_folder"):
                    processed_config["gallery_folder"] = config["gallery_folder"]

                processed_design_images[frame_col][insert_col] = processed_config
        print(f"  🎨 Processed {len(processed_design_images)} frame colors with design_images")

    dto = {
        "id": machine.id,
        "name": machine.name,
        "model": machine.model,
        "frame": machine.frame,
        "frame_color": machine.frame_color,
        "refrigerator": machine.refrigerator,
        "terminal": machine.terminal,
        "price": machine.price,
        "ozon_link": machine.ozon_link,
        "ozon_price": None,
        "graphic_link": machine.graphic_link,
        "main_image": cached_main or main_source_url or machine.main_image,
        "main_image_path": main_source_path,
        "gallery_folder": effective_gallery_folder,
        "description": machine.description,
        "design_images": processed_design_images,
    }
    if include_gallery and effective_gallery_folder:
        cached_gallery = media_cache.get_cached_gallery(machine.id)
        if cached_gallery:
            dto["gallery_files"] = cached_gallery
        else:
            # Если нет кеша, пробуем подтянуть и закешировать на лету
            try:
                folder_path = effective_gallery_folder
                if not folder_path.startswith("/"):
                    folder_path = "/" + folder_path
                items = seafile_client.list_directory(folder_path)
                files = []
                for item in items:
                    if item.get("type") != "file":
                        continue
                    file_path = item.get("path") or f"{folder_path.rstrip('/')}/{item.get('name')}"
                    link = seafile_client.get_file_download_link(file_path)
                    files.append((item.get("name"), link))
                dto["gallery_files"] = media_cache.cache_gallery_files(machine.id, files)
            except Exception:
                dto["gallery_files"] = []
    # Ozon price fetching отключено: ozon_price оставляем None
    return dto


@router.get("/test-design-images")
def test_design_images(db=Depends(get_db)):
    """Тестовый endpoint для проверки design_images"""
    machines = crud.get_coffee_machines(db)
    result = []
    for m in machines:
        if hasattr(m, 'design_images') and m.design_images:
            result.append({
                "id": m.id,
                "name": m.name,
                "design_images_raw": m.design_images,
                "has_design_images": True,
                "frame_colors": list(m.design_images.keys()) if m.design_images else []
            })
    return {"machines_with_design_images": len(result), "data": result}


@router.get("/coffee-machines")
def list_coffee_machines(
    include_gallery: bool = False,
    frame_color: Optional[str] = None,
    insert_color: Optional[str] = None,
    db=Depends(get_db)
):
    machines = crud.get_coffee_machines(db)
    return [machine_to_dict(m, include_gallery=include_gallery, frame_color=frame_color, insert_color=insert_color) for m in machines]


@router.get("/coffee-machines/{machine_id}")
def get_coffee_machine(
    machine_id: int,
    include_gallery: bool = False,
    frame_color: Optional[str] = None,
    insert_color: Optional[str] = None,
    db=Depends(get_db)
):
    machine = crud.get_coffee_machine(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Coffee machine not found")
    return machine_to_dict(machine, include_gallery=include_gallery, frame_color=frame_color, insert_color=insert_color)


@router.get("/models")
def list_models(db=Depends(get_db)):
    return crud.get_models(db)


# Device specs
def spec_to_dict(spec) -> Dict[str, Any]:
    specs_lines = []
    if spec.specs_text:
        specs_lines = [line.strip() for line in spec.specs_text.splitlines() if line.strip()]
    return {
        "id": spec.id,
        "category": spec.category,
        "name": spec.name,
        "title": spec.title,
        "specs_text": spec.specs_text,
        "specs": specs_lines,
        "description": spec.description,
    }


@router.get("/specs")
def list_specs(category: Optional[str] = None, db=Depends(get_db)):
    specs = crud.get_specs(db, category=category)
    return [spec_to_dict(s) for s in specs]


@router.get("/specs/{spec_id}")
def get_spec(spec_id: int, db=Depends(get_db)):
    spec = crud.get_spec(db, spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")
    return spec_to_dict(spec)


@router.get("/specs/by-name")
def get_spec_by_name(category: str, name: str, db=Depends(get_db)):
    spec = crud.get_spec_by_name(db, category, name)
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")
    return spec_to_dict(spec)


@router.get("/config-data")
def get_config_data(db=Depends(get_db)):
    # Легкий агрегированный ответ: машины без галерей и без ozon_price + specs
    machines = crud.get_coffee_machines(db)
    specs = crud.get_specs(db)
    return {
        "machines": [machine_to_dict(m, include_gallery=False, include_ozon_price=False) for m in machines],
        "specs": [spec_to_dict(s) for s in specs],
    }


def send_to_telegram(lead_data: Dict[str, Any]) -> bool:
    """
    Отправляет данные лида в Telegram через бот API
    """
    raw_token = settings.telegram_bot_token
    raw_chat_id = settings.telegram_chat_id
    
    bot_token = str(raw_token or "").strip()
    chat_id = str(raw_chat_id or "").strip()

    # === ИСПРАВЛЕНИЕ: Если в токен попало "ИМЯ_ПЕРЕМЕННОЙ=...", удаляем это ===
    if "=" in bot_token:
        # Разбиваем по знаку '=' и берем вторую часть (само значение)
        bot_token = bot_token.split("=", 1)[1].strip()

    # Убираем префикс bot, если он там оказался
    if bot_token.lower().startswith("bot"):
        bot_token = bot_token[3:]

    if not bot_token or not chat_id:
        print("⚠️  Telegram bot token or chat_id not configured")
        return False
        
    # Формируем URL
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # ВЫВОД В КОНСОЛЬ (Можно удалить потом)
    print("\n" + "="*40)
    print(f"DEBUG: FINAL Cleaned Token: '{bot_token}'")
    print(f"DEBUG: FINAL URL:           '{url}'")
    print("="*40 + "\n")

    message_lines = [
        "🔔 <b>Новая заявка на счёт</b>",
        "",
        f"👤 <b>Имя:</b> {lead_data.get('name', '-')}",
        f"📞 <b>Телефон:</b> {lead_data.get('phone', '-')}",
    ]

    if lead_data.get('telegram'):
        message_lines.append(f"✈️ <b>Telegram:</b> {lead_data.get('telegram')}")

    if lead_data.get('email'):
        message_lines.append(f"📧 <b>Email:</b> {lead_data.get('email')}")

    selection = lead_data.get('selection')
    if selection:
        message_lines.extend([
            "",
            "⚙️ <b>Выбранная конфигурация:</b>",
            f"• Кофемашина: {selection.get('machine', '-')}",
            f"• Каркас: {selection.get('frame', '-')}",
            f"• Цвет каркаса: {selection.get('frame_color', '-')}",
            f"• Холодильник: {selection.get('refrigerator', '-')}",
            f"• Терминал: {selection.get('terminal', '-')}",
            f"• Цена: {selection.get('price', '-')} ₽",
        ])

        if selection.get('ozon_link'):
            message_lines.append(f"• <a href=\"{selection.get('ozon_link')}\">Ссылка на OZON</a>")

    message = "\n".join(message_lines)

    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            print("✓ Message sent to Telegram successfully")
            return True
        else:
            print(f"⚠️  Telegram API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to send to Telegram: {e}")
        return False


@router.post("/lead")
def create_lead(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Создаёт новый лид и отправляет уведомление в Telegram
    """
    try:
        # Извлекаем данные
        name = payload.get("name", "").strip()
        phone = payload.get("phone", "").strip()
        telegram = payload.get("telegram", "").strip()
        email = payload.get("email", "").strip()
        selection = payload.get("selection")

        # Валидация обязательных полей
        if not name or not phone:
            raise HTTPException(status_code=400, detail="Name and phone are required")

        # Создаём запись в БД
        lead = Lead(
            name=name,
            phone=phone,
            telegram=telegram if telegram else None,
            email=email if email else None,
            selection_data=selection
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        # Отправляем в Telegram
        telegram_sent = send_to_telegram({
            "name": name,
            "phone": phone,
            "telegram": telegram,
            "email": email,
            "selection": selection
        })

        return {
            "success": True,
            "id": lead.id,
            "telegram_sent": telegram_sent
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error creating lead: {e}")
        raise HTTPException(status_code=500, detail="Failed to create lead")


@router.get("/ozon-price")
def get_ozon_price(url: str):
    raise HTTPException(status_code=503, detail="Ozon price API temporarily disabled")
