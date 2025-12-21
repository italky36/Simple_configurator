from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from starlette.responses import JSONResponse, RedirectResponse
from datetime import datetime
import os

from .config import Settings
from .database import Base, engine
from sqlalchemy import text
from .routes import router as api_router
from . import models  # noqa: F401

settings = Settings()

app = FastAPI(title="Coffee Machine Configurator Admin")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

Base.metadata.create_all(bind=engine)

# Быстрая миграция: добавляем колонку main_image_path, если её нет
with engine.connect() as conn:
    cols = [row[1] for row in conn.execute(text("PRAGMA table_info(coffee_machines)")).fetchall()]
    if "main_image_path" not in cols:
        try:
            conn.execute(text("ALTER TABLE coffee_machines ADD COLUMN main_image_path VARCHAR(500)"))
        except Exception:
            pass
    if "frame_design_color" not in cols:
        try:
            conn.execute(text("ALTER TABLE coffee_machines ADD COLUMN frame_design_color VARCHAR(100)"))
        except Exception:
            pass


@app.get("/")
def root():
    return RedirectResponse(url="/admin/table")


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if (
        exc.status_code == status.HTTP_401_UNAUTHORIZED
        and not request.url.path.startswith("/login")
        and (request.url.path.startswith("/admin") or request.url.path == "/")
        and "text/html" in (request.headers.get("accept") or "")
    ):
        return RedirectResponse(url="/login", status_code=303)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy():
    """Возвращает страницу политики конфиденциальности"""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "privacy_policy.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        # Подставляем текущую дату
        current_date = datetime.now().strftime("%d.%m.%Y")
        html_content = html_content.replace("{{ current_date }}", current_date)
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Privacy policy not found")


@app.get("/page{page_id}.html", response_class=HTMLResponse)
@app.get("/tilda-block", response_class=HTMLResponse)
@app.get("/configurator", response_class=HTMLResponse)
async def serve_tilda_configurator():
    """Обслуживает страницу конфигуратора Tilda"""
    # Пробуем найти HTML файл в корне проекта
    base_dir = os.path.dirname(os.path.dirname(__file__))
    possible_files = ["tilda_html_block.html", "tilda_block_full.html"]

    for filename in possible_files:
        file_path = os.path.join(base_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())

    raise HTTPException(status_code=404, detail="Configurator page not found")


app.include_router(api_router)
