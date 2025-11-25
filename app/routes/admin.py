import json
from typing import Dict, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from .. import crud
from ..auth import get_current_user
from ..config import Settings
from ..database import get_db
from ..seafile_client import SeafileClient
from ..services import import_export as import_service
from ..services import media_cache

router = APIRouter(prefix="/admin", dependencies=[Depends(get_current_user)])

templates = Jinja2Templates(directory="app/templates")
settings = Settings()
seafile_client = SeafileClient(settings.seafile_server, settings.seafile_repo_id, settings.seafile_token)


@router.get("/")
def admin_dashboard(request: Request, db=Depends(get_db)):
    machines = crud.get_coffee_machines(db, limit=5)
    return templates.TemplateResponse("dashboard.html", {"request": request, "machines": machines})


@router.get("/table")
def admin_table(request: Request, db=Depends(get_db)):
    machines = crud.get_coffee_machines(db)
    return templates.TemplateResponse("table.html", {"request": request, "machines": machines})


@router.get("/specs")
def specs_page(request: Request, db=Depends(get_db)):
    specs = crud.get_specs(db)
    return templates.TemplateResponse("specs.html", {"request": request, "specs": specs})


@router.get("/import_export")
def import_export_page(request: Request):
    return templates.TemplateResponse("import_export.html", {"request": request})


@router.post("/import")
async def import_data(file: UploadFile = File(...), update_existing: bool = True, db=Depends(get_db)):
    result = import_service.import_file(db, file, update_existing=update_existing)
    return JSONResponse({"detail": "Импорт завершен", **result})


@router.get("/export")
def export_data(format: str = "xlsx", db=Depends(get_db)):
    machines = crud.get_coffee_machines(db)
    fmt = format.lower()
    if fmt == "csv":
        buffer = import_service.export_csv(machines)
        return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=coffee_machines.csv"})
    if fmt in ("xlsx", "xlsm"):
        buffer = import_service.export_xlsx(machines)
        return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=coffee_machines.xlsx"})
    raise HTTPException(status_code=400, detail="Поддерживаемые форматы: csv, xlsx")


@router.get("/seafile-browser")
def seafile_browser(path: str = "/"):
    try:
        contents = seafile_client.list_directory(path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Seafile request failed: {exc}")
    return {"path": path, "items": contents}


@router.get("/seafile-file")
def seafile_file(path: str):
    try:
        link = seafile_client.get_file_download_link(path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Seafile request failed: {exc}")
    return {"path": path, "link": link}


def _build_machine_payload(
    name: Optional[str],
    model: Optional[str],
    frame: Optional[str],
    frame_color: Optional[str],
    refrigerator: Optional[str],
    terminal: Optional[str],
    price: Optional[str],
    ozon_link: Optional[str],
    graphic_link: Optional[str],
    main_image: Optional[str],
    main_image_path: Optional[str],
    gallery_folder: Optional[str],
    description: Optional[str],
    clear_main_image: Optional[str] = None,
    clear_main_image_path: Optional[str] = None,
    clear_gallery_folder: Optional[str] = None,
    is_update: bool = False,
) -> dict:
    data = {
        "name": name,
        "model": model,
        "frame": frame,
        "frame_color": frame_color,
        "refrigerator": refrigerator,
        "terminal": terminal,
        "ozon_link": ozon_link,
        "graphic_link": graphic_link,
        "main_image": None if clear_main_image else main_image,
        "main_image_path": None if clear_main_image or clear_main_image_path else main_image_path,
        "gallery_folder": None if clear_gallery_folder else gallery_folder,
        "description": description,
    }

    # При обновлении пустые строки означают "не менять", при создании - "оставить None"
    if not is_update:
        # При создании: пустая строка = None
        for key, value in list(data.items()):
            if isinstance(value, str) and value == "":
                data[key] = None
    else:
        # При обновлении: исключаем пустые строки (не обновляем эти поля)
        data = {k: v for k, v in data.items() if not (isinstance(v, str) and v == "")}
        # Но явно очищенные поля должны быть None
        if clear_main_image:
            data["main_image"] = None
        if clear_main_image_path or clear_main_image:
            data["main_image_path"] = None
        if clear_gallery_folder:
            data["gallery_folder"] = None

    if price not in (None, ""):
        try:
            data["price"] = float(price)
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректное значение цены")
    elif not is_update or price is None:
        data["price"] = None
    # При обновлении, если price пустая строка, не включаем в data (уже исключена выше)

    return data


@router.post("/machine")
def create_machine(
    name: str = Form(...),
    model: Optional[str] = Form(None),
    frame: Optional[str] = Form(None),
    frame_color: Optional[str] = Form(None),
    refrigerator: Optional[str] = Form(None),
    terminal: Optional[str] = Form(None),
    price: Optional[str] = Form(None),
    ozon_link: Optional[str] = Form(None),
    graphic_link: Optional[str] = Form(None),
    main_image: Optional[str] = Form(None),
    main_image_path: Optional[str] = Form(None),
    gallery_folder: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    clear_main_image: Optional[str] = Form(None),
    clear_main_image_path: Optional[str] = Form(None),
    clear_gallery_folder: Optional[str] = Form(None),
    db=Depends(get_db),
):
    payload = _build_machine_payload(
        name,
        model,
        frame,
        frame_color,
        refrigerator,
        terminal,
        price,
        ozon_link,
        graphic_link,
        main_image,
        main_image_path,
        gallery_folder,
        description,
        clear_main_image,
        clear_main_image_path,
        clear_gallery_folder,
        is_update=False,
    )
    machine = crud.create_coffee_machine(db, payload)
    media_cache.cache_machine_media(machine, seafile_client)
    return {"detail": "Создано", "id": machine.id}


@router.post("/machine/{machine_id}")
def update_machine(
    machine_id: int,
    name: str = Form(...),
    model: Optional[str] = Form(None),
    frame: Optional[str] = Form(None),
    frame_color: Optional[str] = Form(None),
    refrigerator: Optional[str] = Form(None),
    terminal: Optional[str] = Form(None),
    price: Optional[str] = Form(None),
    ozon_link: Optional[str] = Form(None),
    graphic_link: Optional[str] = Form(None),
    main_image: Optional[str] = Form(None),
    main_image_path: Optional[str] = Form(None),
    gallery_folder: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    clear_main_image: Optional[str] = Form(None),
    clear_main_image_path: Optional[str] = Form(None),
    clear_gallery_folder: Optional[str] = Form(None),
    db=Depends(get_db),
):
    payload = _build_machine_payload(
        name,
        model,
        frame,
        frame_color,
        refrigerator,
        terminal,
        price,
        ozon_link,
        graphic_link,
        main_image,
        main_image_path,
        gallery_folder,
        description,
        clear_main_image,
        clear_main_image_path,
        clear_gallery_folder,
        is_update=True,
    )

    updated = crud.update_coffee_machine(db, machine_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Coffee machine not found")
    media_cache.cache_machine_media(updated, seafile_client)
    return {"detail": "Обновлено", "id": updated.id}


@router.post("/machine/{machine_id}/delete")
def delete_machine(machine_id: int, db=Depends(get_db)):
    deleted = crud.delete_coffee_machine(db, machine_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Coffee machine not found")
    media_cache.clear_machine_cache(machine_id)
    return {"detail": "Удалено", "id": machine_id}


@router.post("/machines/bulk-delete")
async def bulk_delete(request: Request, db=Depends(get_db)):
    body_bytes = await request.body()
    payload: Dict = {}
    if body_bytes:
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            payload = {}
    ids = payload.get("ids") if isinstance(payload, dict) else None
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="ids должен быть списком")
    deleted = 0
    for machine_id in ids:
        if crud.delete_coffee_machine(db, machine_id):
            deleted += 1
    return {"detail": "Удалено", "deleted": deleted, "requested": len(ids)}


@router.post("/update-image/{machine_id}")
def update_image(
    machine_id: int,
    main_image: Optional[str] = Form(None),
    main_image_path: Optional[str] = Form(None),
    gallery_folder: Optional[str] = Form(None),
    db=Depends(get_db),
):
    update_data = {}
    if main_image is not None:
        update_data["main_image"] = main_image
    if main_image_path is not None:
        update_data["main_image_path"] = main_image_path
    if gallery_folder is not None:
        update_data["gallery_folder"] = gallery_folder
    updated = crud.update_coffee_machine(db, machine_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Coffee machine not found")
    media_cache.cache_machine_media(updated, seafile_client)
    return {"detail": "Images updated", "item": {"id": updated.id, "main_image": updated.main_image, "gallery_folder": updated.gallery_folder}}


# Specs admin
@router.post("/spec")
def create_spec(
    category: str = Form(...),
    name: str = Form(...),
    specs_text: Optional[str] = Form(None),
    db=Depends(get_db),
):
    payload = {"category": category, "name": name, "title": name, "specs_text": specs_text or "", "description": ""}
    spec = crud.create_spec(db, payload)
    return {"detail": "Создано", "id": spec.id}


@router.post("/spec/{spec_id}")
def update_spec(
    spec_id: int,
    category: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    specs_text: Optional[str] = Form(None),
    db=Depends(get_db),
):
    payload = {
        "category": category,
        "name": name,
        "title": name,
        "specs_text": specs_text,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    updated = crud.update_spec(db, spec_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Spec not found")
    return {"detail": "Обновлено", "id": updated.id}


@router.post("/spec/{spec_id}/delete")
def delete_spec(spec_id: int, db=Depends(get_db)):
    deleted = crud.delete_spec(db, spec_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Spec not found")
    return {"detail": "Удалено", "id": spec_id}


@router.post("/specs/bulk-delete")
async def bulk_delete_specs(request: Request, db=Depends(get_db)):
    body_bytes = await request.body()
    payload: Dict = {}
    if body_bytes:
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            payload = {}
    ids = payload.get("ids") if isinstance(payload, dict) else None
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="ids должен быть списком")
    deleted = 0
    for spec_id in ids:
        if crud.delete_spec(db, spec_id):
            deleted += 1
    return {"detail": "Удалено", "deleted": deleted, "requested": len(ids)}


@router.post("/specs/auto-populate")
def auto_populate_specs(db=Depends(get_db)):
    machines = crud.get_coffee_machines(db, limit=10_000)
    created = 0
    skip_values = {"да", "нет", "-", "none", ""}
    mapping = {
        "coffee_machine": lambda m: m.model or m.name,
        "frame": lambda m: m.frame,
        "refrigerator": lambda m: m.refrigerator,
        "terminal": lambda m: m.terminal,
    }
    for category, getter in mapping.items():
        seen = set()
        for m in machines:
            value = getter(m)
            if not value:
                continue
            value_str = str(value).strip()
            if not value_str or value_str.lower() in skip_values:
                continue
            if (category, value_str) in seen:
                continue
            seen.add((category, value_str))
            existing = crud.get_spec_by_name(db, category, value_str)
            if existing:
                continue
            crud.create_spec(db, {"category": category, "name": value_str, "title": value_str, "specs_text": "", "description": ""})
            created += 1
    return {"detail": "Генерация завершена", "created": created}
