from typing import Any, Dict, List, Optional
import requests

from fastapi import APIRouter, Depends, HTTPException

from .. import crud
from ..config import Settings
from ..database import get_db
from ..seafile_client import SeafileClient

router = APIRouter(prefix="/api")
settings = Settings()
seafile_client = SeafileClient(settings.seafile_server, settings.seafile_repo_id, settings.seafile_token)


def machine_to_dict(machine, include_gallery: bool = False) -> Dict[str, Any]:
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
        "graphic_link": machine.graphic_link,
        "main_image": machine.main_image,
        "gallery_folder": machine.gallery_folder,
        "description": machine.description,
    }
    if include_gallery and machine.gallery_folder:
        try:
            dto["gallery_files"] = seafile_client.list_file_links(machine.gallery_folder)
        except Exception:
            dto["gallery_files"] = []
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
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise HTTPException(status_code=500, detail="Telegram not configured")
    msg = _build_lead_message(payload)
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": settings.telegram_chat_id, "text": msg},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to send to Telegram: {exc}")
    return {"detail": "ok"}
