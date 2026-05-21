# План доработки ebook-meta-helper

> Обновлено: 2026-05-21
> Ветка разработки: `feat/db_front`
> Предыдущая версия плана: 2026-03-14

## Идея проекта

Инструмент для массового обогащения метаданных электронных книг с помощью AI.
Тысячи книг (EPUB, FB2) с неполными метаданными не распознаются Booklore.
Скрипт читает содержимое книги и структуру директорий (например, `Warhammer 40k/Ересь Хоруса/название`) — это уже даёт достаточно контекста для AI, чтобы найти автора, серию, описание, теги и обложку.

Веб-интерфейс позволяет видеть все файлы, сравнивать оригинальные и AI-найденные метаданные, принимать или отклонять предложения AI, перезапускать обработку отдельных файлов.

---

## Принятые архитектурные решения

| Решение | Выбор | Обоснование |
|---------|-------|-------------|
| Frontend-фреймворк | **Vue 3 + Vite** | Изначальный план, area.yml настроен под Vue |
| CSS | **Pico CSS** | Минималистично, без классов, не мешает |
| AI-контекст соседних книг | **Directory hints** | AI сначала суммаризирует директорию целиком, сохраняет результат в БД, потом каждая книга получает этот summary как контекст |
| База данных | **MariaDB** | Два писателя (api + watcher), FK-heavy схема, Alembic-миграции уже под MySQL |
| Контейнеры | **Два сервиса** (`api` + `watcher`) | Один образ, раздельные логи и restart-политики |
| Миграции | **Auto на старте `api`** | Идемпотентный `alembic upgrade head` через entrypoint |

---

## Текущий статус

| Фаза | Описание | Статус |
|------|----------|--------|
| 0 | Подготовка | ✅ Готово |
| 1 | Перенос в `apps/` | ✅ Готово |
| 2 | Слой БД (Directory, FileRecord, Metadata) + Alembic | ✅ Готово |
| 3 | Обогащение схемы БД + репозитории | 🔲 Не начато |
| 4 | Интеграция пайплайна с БД + directory hints | 🔲 Не начато |
| 5 | API endpoints | 🔲 Не начато |
| 6 | Фронтенд (Vue 3) | 🔲 Не начато |
| 7 | Docker и инфра | 🔲 Не начато |

**Порядок выполнения:** 3 → 4 → 5 и 6 параллельно → 7

---

## Фаза 3: Обогащение схемы БД

### 3.1 Изменения существующих моделей

**`db/models/directory.py`** — добавить:
```python
hints = Column(JSON, nullable=True)  # AI-summary директории
```

**`db/models/file_record.py`** — добавить:
```python
class FileStatus(str, enum.Enum):
    pending    = "pending"
    scanning   = "scanning"
    ai_queued  = "ai_queued"
    enriching  = "enriching"
    enriched   = "enriched"
    accepted   = "accepted"
    failed     = "failed"

status        = Column(Enum(FileStatus), default=FileStatus.pending, nullable=False)
error_message = Column(Text, nullable=True)
```

**`db/models/metadata.py`** — добавить поля:
```python
enrichment_run_id    = Column(Integer, ForeignKey("enrichment_runs.id"), nullable=True)
is_current           = Column(Boolean, default=True, nullable=False)
data_schema_version  = Column(String(16), default="1", nullable=False)
```

### 3.2 Новые модели

**`db/models/enrichment_run.py`**
```python
class EnrichmentRun(Base):
    __tablename__ = "enrichment_runs"
    id           = Column(Integer, primary_key=True)
    directory_id = Column(Integer, ForeignKey("directories.id"), nullable=False)
    status       = Column(String(32), default="running")  # running/done/failed
    model        = Column(String(64))
    started_at   = Column(DateTime, default=datetime.utcnow)
    finished_at  = Column(DateTime, nullable=True)
```

**`db/models/processing_log.py`**
```python
class ProcessingLog(Base):
    __tablename__ = "processing_logs"
    id             = Column(Integer, primary_key=True)
    file_record_id = Column(Integer, ForeignKey("file_records.id"), nullable=False)
    step           = Column(String(64))   # scan/read/clean/ai_enrich/merge/write/move
    status         = Column(String(16))   # ok/error/skip
    message        = Column(Text, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
```

### 3.3 Репозитории

**Структура `db/repos/`:**
```
db/repos/
├── __init__.py
├── directory_repo.py      # CRUD для Directory, update hints
├── file_repo.py           # CRUD для FileRecord, смена статуса
├── metadata_repo.py       # CRUD для Metadata, is_current management
├── enrichment_run_repo.py # создание/завершение EnrichmentRun
└── log_repo.py            # запись шагов ProcessingLog
```

### 3.4 Миграции

- `004_add_directory_hints.py`
- `005_add_file_record_status.py`
- `006_create_enrichment_runs.py`
- `007_create_processing_logs.py`
- `008_extend_metadata.py`

### 3.5 Задачи

- [ ] Добавить `Directory.hints`
- [ ] Добавить `FileStatus` enum + поля в `FileRecord`
- [ ] Добавить поля `enrichment_run_id`, `is_current`, `data_schema_version` в `Metadata`
- [ ] Создать `db/models/enrichment_run.py`
- [ ] Создать `db/models/processing_log.py`
- [ ] Обновить `db/models/__init__.py`
- [ ] Создать миграции 004–008
- [ ] Создать все репозитории в `db/repos/`
- [ ] Покрыть репозитории интеграционными тестами

---

## Фаза 4: Интеграция пайплайна с БД + directory hints

### 4.1 DB-driven пайплайн

Сейчас `watcher.py` обрабатывает файлы независимо от БД. После доработки:

1. Сканирование директории → создать/обновить `Directory` + `FileRecord` (status=`pending`)
2. Каждый шаг обработки → обновлять `FileRecord.status` + писать в `ProcessingLog`
3. `process_file.py` разбить на явные шаги с DB-транзакцией вокруг каждого:
   ```
   scan → read_metadata → clean → ai_enrich → merge → write → move
   ```
4. AI/сетевые вызовы — **вне транзакций** (транзакция только при записи результата)

### 4.2 Directory hints (мультифайловый контекст)

Добавить в `AIProvider`:
```python
async def summarize_directory(self, files: list[BookRecord]) -> dict:
    """
    Анализирует все книги в директории, возвращает JSON с:
    - series_name, universe, genre, tags, language
    - Вызывается один раз перед обработкой директории
    """
```

Порядок работы:
1. Перед обработкой директории — вызвать `summarize_directory(all_files_in_dir)`
2. Сохранить результат в `Directory.hints`
3. При enrichment каждой книги — добавить `directory.hints` в промпт как контекст

### 4.3 Изменения в `watcher.py`

```
Цикл по директориям:
  1. Скан → FileRecord[] в БД (status=pending)
  2. summarize_directory() → Directory.hints
  3. Для каждого файла:
       enrich(book, hints=directory.hints)
       → update status → log steps
```

### 4.4 Задачи

- [ ] Добавить `summarize_directory()` в `AIProvider` (base + openai + dummy)
- [ ] Рефакторинг `process_file.py` — шаги с явными DB-переходами
- [ ] Обновить `watcher.py` — DB-driven цикл + directory hints
- [ ] При каждом шаге писать в `ProcessingLog`
- [ ] Добавить тесты для нового пайплайна (с DummyProvider)

---

## Фаза 5: API endpoints

### 5.1 Структура

```
apps/backend/app/api/
├── __init__.py
├── main.py           # FastAPI app, подключение роутов + статика
├── deps.py           # get_db()
├── schemas.py        # Pydantic-схемы (никогда ORM напрямую)
└── routes/
    ├── __init__.py
    ├── directories.py
    ├── files.py
    └── scan.py
```

### 5.2 Эндпоинты

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/api/health` | GET | ✅ Уже есть |
| `/api/directories` | GET | Дерево директорий со статистикой |
| `/api/directories/{id}` | GET | Директория + список файлов со статусами |
| `/api/directories/{id}/scan` | POST | Запустить сканирование + AI enrichment |
| `/api/files` | GET | Список файлов (пагинация, фильтр по статусу) |
| `/api/files/{id}` | GET | Файл с текущими метаданными |
| `/api/files/{id}/metadata` | GET | История всех версий метаданных |
| `/api/files/{id}/accept` | POST | Принять AI-предложение → записать в файл |
| `/api/files/{id}/reject` | POST | Отклонить, оставить оригинал |
| `/api/files/{id}/enrich` | POST | Перезапустить AI для конкретного файла |
| `/api/scan/status` | GET | Статус текущей задачи сканирования |

### 5.3 Раздача фронтенда из FastAPI

```python
# apps/backend/app/api/main.py
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

FRONTEND_DIR = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(FRONTEND_DIR / "index.html")
```

### 5.4 Задачи

- [ ] Создать `apps/backend/app/api/deps.py`
- [ ] Создать `apps/backend/app/api/schemas.py` (Pydantic-схемы для всех ответов)
- [ ] Создать `apps/backend/app/api/routes/directories.py`
- [ ] Создать `apps/backend/app/api/routes/files.py`
- [ ] Создать `apps/backend/app/api/routes/scan.py`
- [ ] Обновить `apps/backend/app/api/main.py` — роутеры + раздача статики
- [ ] Добавить интеграционные тесты для API

---

## Фаза 6: Фронтенд (Vue 3)

### 6.1 Замена React → Vue 3

Текущий `apps/frontend/` (React) удалить и пересоздать на Vue 3 + Vite:

```bash
cd apps
npm create vue@latest frontend
# Выбрать: Vue Router, без TypeScript (или с — на усмотрение)
cd frontend && npm install @picocss/pico
```

### 6.2 Структура страниц

```
apps/frontend/src/
├── main.js
├── App.vue              # Layout + router-view
├── router/index.js
├── api/index.js         # fetch-обёртка для бэкенда
└── pages/
    ├── DirectoriesPage.vue   # Дерево директорий, кнопка Scan
    ├── FilesPage.vue         # Список файлов директории, фильтр по статусу
    ├── FileDetailPage.vue    # История мета: original → AI → diff; Accept/Reject/Re-run
    └── ScanPage.vue          # Прогресс сканирования, лог шагов
```

### 6.3 Ключевой экран: FileDetailPage

Центральный экран продукта. Показывает:
- Оригинальные метаданные из файла (`source: file_original`)
- Что предложил AI (`source: ai_enriched`) — diff с подсветкой изменений
- Кнопки: **Принять** / **Отклонить** / **Перезапустить AI**
- Историю всех версий

### 6.4 Задачи

- [ ] Инициализировать Vue 3 + Vite в `apps/frontend/` (удалить React-заглушку)
- [ ] Установить Pico CSS + vue-router
- [ ] Создать `api/index.js` — fetch-обёртка
- [ ] Реализовать `DirectoriesPage.vue`
- [ ] Реализовать `FilesPage.vue`
- [ ] Реализовать `FileDetailPage.vue` (diff-просмотр + Accept/Reject)
- [ ] Реализовать `ScanPage.vue`
- [ ] Добавить скрипт сборки в workflow

---

## Фаза 7: Docker и инфра

### 7.1 Dockerfile (переехать в корень проекта)

```dockerfile
# Сборка фронтенда
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY apps/frontend/package*.json ./
RUN npm ci
COPY apps/frontend/ ./
RUN npm run build

# Backend runtime
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY apps/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/backend/app/ app/
COPY apps/backend/db/ db/
COPY apps/backend/alembic/ alembic/
COPY apps/backend/alembic.ini .
COPY apps/backend/run_watcher.py apps/backend/run_api.py apps/backend/run_scan.py ./
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-u", "run_api.py"]
```

**`docker-entrypoint.sh`:**
```bash
#!/usr/bin/env sh
set -eu
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    alembic upgrade head
fi
exec "$@"
```

### 7.2 docker-compose.yml (два сервиса)

```yaml
services:
  api:
    build: { context: ., dockerfile: Dockerfile }
    image: ebook-meta-helper:latest
    environment:
      RUN_MIGRATIONS: "1"
      DB_HOST: mariadb
    env_file: .env
    ports:
      - "${API_PORT:-8000}:8000"
    volumes:
      - ${HOST_NEW_BOOKS_DIR}:/data/new_books
      - ${HOST_BOOKS_READY_DIR}:/data/books_ready
      - ${HOST_DEBUG_DIR:-./debug_logs}:/app/debug_logs
    depends_on:
      mariadb:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health').read()"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s

  watcher:
    image: ebook-meta-helper:latest
    command: ["python", "-u", "run_watcher.py"]
    env_file: .env
    environment:
      DB_HOST: mariadb
    volumes:
      - ${HOST_NEW_BOOKS_DIR}:/data/new_books
      - ${HOST_BOOKS_READY_DIR}:/data/books_ready
      - ${HOST_DEBUG_DIR:-./debug_logs}:/app/debug_logs
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped

  mariadb:
    image: mariadb:11
    environment:
      MARIADB_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MARIADB_DATABASE: ${DB_NAME:-ebook_meta}
      MARIADB_USER: ${DB_USER:-ebook}
      MARIADB_PASSWORD: ${DB_PASSWORD}
    volumes:
      - mariadb_data:/var/lib/mysql
    ports:
      - "127.0.0.1:${DB_PORT:-3306}:3306"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "mysql -u root -p\"$$MARIADB_ROOT_PASSWORD\" -e 'SELECT 1' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  mariadb_data:
```

### 7.3 .env.example (обновить)

```env
# === Пути на хосте (обязательно задать перед первым запуском) ===
HOST_NEW_BOOKS_DIR=    # абсолютный путь, например /mnt/nas/books/inbox
HOST_BOOKS_READY_DIR=  # абсолютный путь, например /mnt/nas/books/ready
HOST_DEBUG_DIR=./debug_logs

# === API ===
API_PORT=8000

# === База данных (пароли обязательно сменить!) ===
DB_NAME=ebook_meta
DB_USER=ebook
DB_PASSWORD=           # ЗАДАТЬ обязательно
DB_ROOT_PASSWORD=      # ЗАДАТЬ обязательно
DB_PORT=3306

# === AI ===
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
AI_PROVIDER=openai     # openai | dummy

# === Директории внутри контейнера (не менять) ===
NEW_BOOKS_DIR=/data/new_books
BOOKS_READY_DIR=/data/books_ready
DEBUG_DIR=/app/debug_logs

# === Именование файлов ===
FILENAME_TEMPLATE={Authors} - {Title}
```

### 7.4 .dockerignore (перенести в корень, расширить)

```
apps/frontend/node_modules
apps/frontend/dist
apps/backend/__pycache__
apps/backend/.pytest_cache
apps/backend/tests
docs
.git
.env
*.md
```

### 7.5 Задачи

- [ ] Переместить `Dockerfile` из `apps/backend/` в корень проекта
- [ ] Написать `docker-entrypoint.sh`
- [ ] Обновить `docker-compose.yml` — два сервиса, bind mounts, 127.0.0.1 для MariaDB
- [ ] Перенести и расширить `.dockerignore` в корень
- [ ] Обновить `.env.example` — `HOST_*` переменные, убрать дефолты для паролей
- [ ] Проверить: `docker compose up --build`, `/api/health`, watcher логи
- [ ] Заполнить `.claude/devops/environments.md` (prod-хост, механика деплоя, бэкап БД)

---

## Чеклист для PR

- [ ] Все тесты проходят (`just test` или `pytest` в контейнере)
- [ ] Линтер без ошибок (`ruff check`)
- [ ] Миграции применяются (`alembic upgrade head`)
- [ ] Docker собирается (`docker compose build`)
- [ ] API отвечает (`/api/health`)
- [ ] Фронт открывается (`/`)
- [ ] `HOST_NEW_BOOKS_DIR` не задан → `docker compose up` падает с ошибкой (fail-fast)
- [ ] Watcher логи появляются в `HOST_DEBUG_DIR` на хосте
