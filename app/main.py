from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse, RedirectResponse

from .config import Settings
from .database import Base, engine
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


app.include_router(api_router)
