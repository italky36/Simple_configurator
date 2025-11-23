from sqlalchemy import Column, Float, Integer, String, Text

from .database import Base


class CoffeeMachine(Base):
    __tablename__ = "coffee_machines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    model = Column(String(100))
    # Основные характеристики
    frame = Column(String(100))  # Каркас
    frame_color = Column(String(100))  # Цвет каркаса
    refrigerator = Column(String(100))  # Холодильник
    terminal = Column(String(100))  # Терминал
    price = Column(Float)
    # Ссылки
    ozon_link = Column(String(500))
    graphic_link = Column(String(500))
    main_image = Column(String(500))
    gallery_folder = Column(String(500))
    description = Column(Text)


class DeviceSpec(Base):
    __tablename__ = "device_specs"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False)  # e.g., coffee_machine, terminal, refrigerator
    name = Column(String(255), nullable=False, index=True)  # уникальное имя компонента/устройства
    title = Column(String(255))  # человекочитаемое название (можно не использовать)
    specs_text = Column(Text, nullable=True)  # характеристики построчно
    description = Column(Text)
