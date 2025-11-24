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
    include_ozon_price: bool = True,
) -> Dict[str, Any]:
    cached_main = media_cache.get_cached_main(machine.id)
    if not cached_main and machine.main_image:
        cached_main = media_cache.cache_main_image(machine.id, machine.main_image)

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
        "main_image": cached_main or machine.main_image,
        "gallery_folder": machine.gallery_folder,
        "description": machine.description,
    }
    if include_gallery and machine.gallery_folder:
        cached_gallery = media_cache.get_cached_gallery(machine.id)
        if cached_gallery:
            dto["gallery_files"] = cached_gallery
        else:
            # Если нет кеша, пробуем подтянуть и закешировать на лету
            try:
                folder_path = machine.gallery_folder
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
    if include_ozon_price and machine.ozon_link and ozon_client:
        try:
            price_data = ozon_client.get_price_by_url(machine.ozon_link)
            if price_data:
                dto["ozon_price"] = price_data.get("price")
        except Exception:
            dto["ozon_price"] = None
    return dto


@router.get("/coffee-machines")
def list_coffee_machines(include_gallery: bool = False, db=Depends(get_db)):
    machines = crud.get_coffee_machines(db)
    return [machine_to_dict(m, include_gallery=include_gallery) for m in machines]


@router.get("/coffee-machines/{machine_id}")
def get_coffee_machine(machine_id: int, include_gallery: bool = False, db=Depends(get_db)):
    machine = crud.get_coffee_machine(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Coffee machine not found")
    return machine_to_dict(machine, include_gallery=include_gallery)


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
    if not ozon_client:
        raise HTTPException(status_code=500, detail="Ozon API not configured")

    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")

    try:
        result = ozon_client.get_price_by_url(url)
        if not result:
            return {"found": False, "price": None, "currency": None, "name": None}

        return {
            "found": True,
            "price": result.get("price"),
            "currency": result.get("currency", "RUB"),
            "name": result.get("name"),
            "product_id": result.get("product_id"),
            "offer_id": result.get("offer_id"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Ozon price: {exc}")
