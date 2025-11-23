# Coffee Machine Configurator Admin

FastAPI + Bootstrap админка для управления кофемашинами с интеграцией Seafile и публичным API.

## Быстрый старт
- Скопируйте `.env.example` в `.env` и заполните значения.
- Создайте виртуальное окружение и установите зависимости: `pip install -r requirements.txt`.
- Инициализируйте базу и тестовые данные (SQLite по умолчанию): `python scripts/init_db.py`.
- Запустите приложение: `uvicorn app.main:app --reload`.
- Админка доступна по `/admin/` (HTTP Basic Auth).

## Структура
- `app/main.py` – создание FastAPI, CORS, роуты, подключение статики.
- `app/config.py` – настройки из `.env`.
- `app/database.py` – соединение с БД и session dependency.
- `app/models.py` – модель `CoffeeMachine` с полями `main_image` и `gallery_folder`.
- `app/crud.py` – базовые CRUD-операции.
- `app/seafile_client.py` – обертка над Seafile API.
- `app/routes/` – админские и публичные endpoints, шаблоны в `app/templates`.
- `scripts/init_db.py` – создание таблиц и заполнение демо-данными (не вставляет повторно, если записи уже есть).
- `app/services/import_export.py` – импорт CSV/XLSX и экспорт в CSV/XLSX без pandas.

## Следующие шаги
- Добавить формы CRUD в шаблоны и валидацию.
- Расширить Seafile браузер с выбором главного изображения.
