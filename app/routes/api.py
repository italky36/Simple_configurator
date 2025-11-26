from typing import Any, Dict, List, Optional
import requests

from fastapi import APIRouter, Depends, HTTPException

from .. import crud
from ..config import Settings
from ..database import get_db
from ..seafile_client import SeafileClient
from ..ozon_client import OzonClient
from ..services import media_cache

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

    # Получаем ссылку из Seafile
    cached_main = media_cache.get_cached_main(machine.id)
    if main_source_path:
        try:
            main_source_url = seafile_client.get_file_download_link(main_source_path)
        except Exception:
            main_source_url = main_source_path

    if not cached_main and main_source_url:
        cached_main = media_cache.cache_main_image(machine.id, main_source_url)

    # Используем переопределенную gallery_folder если есть
    effective_gallery_folder = gallery_folder_override or machine.gallery_folder

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
        "design_images": machine.design_images if hasattr(machine, 'design_images') else None,
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


def _build_lead_message(payload: Dict[str, Any]) -> str:
    phone = payload.get("phone") or "-"
    tg = payload.get("telegram") or "-"
    sel = payload.get("selection") or {}
    lines = [
        "Новая заявка с конфигуратора",
        f"Телефон: {phone}",
        f"Telegram: {tg}",
        "",
        "Выбор пользователя:",
        f"Кофемашина: {sel.get('machine') or '-'}",
        f"Каркас: {sel.get('frame') or '-'}",
        f"Цвет каркаса: {sel.get('frame_color') or '-'}",
        f"Холодильник: {sel.get('refrigerator') or '-'}",
        f"Терминал: {sel.get('terminal') or '-'}",
        f"Цена: {sel.get('price') or '-'}",
        f"OZON: {sel.get('ozon_link') or '-'}",
        f"Gallery: {sel.get('gallery_folder') or '-'}",
    ]
    return "\n".join(lines)


@router.post("/lead")
def lead(payload: Dict[str, Any]):
    # Публичные записи через API временно запрещены
    raise HTTPException(status_code=403, detail="Writing through public API is disabled")


@router.get("/ozon-price")
def get_ozon_price(url: str):
    raise HTTPException(status_code=503, detail="Ozon price API temporarily disabled")
