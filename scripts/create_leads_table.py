#!/usr/bin/env python3
"""
Скрипт для создания таблицы leads
"""
import sqlite3
import os
import sys

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "coffee_machines.db")


def create_leads_table():
    """Создаёт таблицу leads если её нет"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Проверяем существование таблицы
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='leads'"
    )
    if cursor.fetchone():
        print("✓ Таблица leads уже существует")
        conn.close()
        return

    # Создаём таблицу
    cursor.execute("""
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            telegram VARCHAR(255),
            email VARCHAR(255),
            selection_data TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("✓ Таблица leads создана успешно")


if __name__ == "__main__":
    create_leads_table()
