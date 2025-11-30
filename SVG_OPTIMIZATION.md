# SVG Optimization

## Проблема
SVG файлы очень большие (8.5 МБ каждый) из-за:
- Встроенных растровых изображений в base64
- Неоптимизированного кода
- Лишних метаданных и комментариев

## Решение

### 1. Установить scour (SVG оптимизатор)

```bash
pip install scour
```

### 2. Пересоздать кэш

Удалите старый кэш и запустите скрипт заново:

```bash
# Удалить старый кэш
rm -rf /srv/Simple_configurator/app/static/cache/machines/*

# Запустить скрипт заново для пересоздания с оптимизацией
cd /srv/Simple_configurator
python scripts/auto_assign_design_images.py --verbose
```

### 3. Результат

Скрипт теперь автоматически оптимизирует все SVG файлы при скачивании:
- Удаляет комментарии и метаданные
- Укорачивает ID элементов
- Убирает лишние пробелы
- Обычно уменьшает размер на 20-50%

## Альтернатива: Gzip compression на сервере

Если установка scour невозможна, включите Gzip сжатие для SVG на веб-сервере:

### Nginx:
```nginx
gzip on;
gzip_types image/svg+xml;
gzip_vary on;
```

### Apache:
```apache
AddOutputFilterByType DEFLATE image/svg+xml
```

Это уменьшит размер передачи на 70-90% без изменения файлов.
