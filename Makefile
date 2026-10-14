.PHONY: clean

# Удаляет только генерируемые кэши и артефакты сборки Python.
clean:
	@echo "Удаляю кэши и артефакты сборки Python..."
	@find . \( -type d \( -name .git -o -name .venv -o -name venv \) -prune \) -o \( -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache -o -name htmlcov -o -name '*.egg-info' -o -name build -o -name dist \) -prune -exec rm -rf {} + \)
	@find . \( -type d \( -name .git -o -name .venv -o -name venv \) -prune \) -o \( -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyd' \) -exec rm -f {} + \)
	@rm -f .coverage coverage.xml
	@echo "Готово. .venv, .env и данные PostgreSQL не затронуты."
