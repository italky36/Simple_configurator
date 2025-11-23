from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import make_login_response, make_logout_response, verify_credentials

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        verify_credentials(type("cred", (), {"username": username, "password": password}))
    except Exception:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный логин или пароль"}, status_code=401)
    resp = RedirectResponse(url="/admin/", status_code=303)
    return make_login_response(resp, username)


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    return make_logout_response(resp)
