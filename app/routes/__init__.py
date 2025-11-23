from fastapi import APIRouter

from . import admin, api, auth

router = APIRouter()
router.include_router(auth.router, tags=["auth"])
router.include_router(admin.router, tags=["admin"])
router.include_router(api.router, tags=["public"])
