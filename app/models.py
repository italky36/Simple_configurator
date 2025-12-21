from sqlalchemy import Column, Float, Integer, String, Text, DateTime
from sqlalchemy.types import JSON
from datetime import datetime

from .database import Base


class CoffeeMachine(Base):
    __tablename__ = "coffee_machines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    model = Column(String(100))
    # Основные характеристики
    frame = Column(String(100))  # Каркас
    frame_color = Column(String(100))  # Цвет каркаса
    frame_design_color = Column(String(100))  # Цвет дизайна каркаса (акцентные вставки для OZON)
    refrigerator = Column(String(100))  # Холодильник
    terminal = Column(String(100))  # Терминал
    price = Column(Float)
    # Ссылки
    ozon_link = Column(String(500))
    graphic_link = Column(String(500))
    main_image = Column(String(500))
    # Путь в Seafile (чтобы можно было получить свежую ссылку при протухшем токене)
    main_image_path = Column(String(500))
    gallery_folder = Column(String(500))
    description = Column(Text)
    # Фото для комбинаций цвета корпуса и цвета вставки
    # Структура: {"белый": {"жёлтый": {"main_image": "...", "main_image_path": "...", "gallery_folder": "..."}, ...}, "чёрный": {...}}
    design_images = Column(JSON, nullable=True)


class DeviceSpec(Base):
    __tablename__ = "device_specs"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False)  # e.g., coffee_machine, terminal, refrigerator
    name = Column(String(255), nullable=False, index=True)  # уникальное имя компонента/устройства
    title = Column(String(255))  # человекочитаемое название (можно не использовать)
    specs_text = Column(Text, nullable=True)  # характеристики построчно
    description = Column(Text)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    telegram = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    selection_data = Column(JSON, nullable=True)  # Данные о выбранной конфигурации
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
