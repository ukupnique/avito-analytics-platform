.DEFAULT_GOAL := help

PYTHON ?= .venv/bin/python
PYTHON_PATHS ?= backend alembic
PYTEST_ARGS ?=
RUFF_CONFIG := backend/pyproject.toml

.PHONY: help install-dev format lint up stop down test clean

help:
	@echo "make install-dev  Установить зависимости для разработки в .venv"
	@echo "make format       Исправить форматирование Python-кода и порядок импортов"
	@echo "make lint         Проверить Python-код линтером Ruff"
	@echo "make up           Запустить все сервисы Compose и дождаться их готовности"
	@echo "make stop         Остановить контейнеры без удаления"
	@echo "make down         Остановить и удалить контейнеры, сохранив данные БД"
	@echo "make test         Запустить pytest (БД должна быть запущена)"
	@echo "make clean        Удалить генерируемые кэши и артефакты Python"

install-dev:
	$(PYTHON) -m pip install -e './backend[dev]'

# Сначала сортирует импорты, затем исправляет пробелы, переносы и отступы.
format:
	$(PYTHON) -m ruff check --config $(RUFF_CONFIG) --select I --fix $(PYTHON_PATHS)
	$(PYTHON) -m ruff format --config $(RUFF_CONFIG) $(PYTHON_PATHS)

lint:
	$(PYTHON) -m ruff check --config $(RUFF_CONFIG) $(PYTHON_PATHS)

up:
	docker compose up -d --wait --wait-timeout 60

stop:
	docker compose stop

# Без --volumes: данные PostgreSQL сохраняются между запусками.
down:
	docker compose down

test:
	DEBUG=false PYTHONPATH=backend $(PYTHON) -m pytest -q $(PYTEST_ARGS)

# Удаляет только генерируемые кэши и артефакты сборки Python.
clean:
	@echo "Удаляю кэши и артефакты сборки Python..."
	@find . \( -type d \( -name .git -o -name .venv -o -name venv \) -prune \) -o \( -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache -o -name htmlcov -o -name '*.egg-info' -o -name build -o -name dist \) -prune -exec rm -rf {} + \)
	@find . \( -type d \( -name .git -o -name .venv -o -name venv \) -prune \) -o \( -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyd' \) -exec rm -f {} + \)
	@rm -f .coverage coverage.xml
	@echo "Готово. .venv, .env и данные PostgreSQL не затронуты."
