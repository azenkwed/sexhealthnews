.PHONY: run admin install reset trigger kill venv icons test db db-stop db-reset

PORT     ?= 8000
VENV     := .venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
ICON_SRC ?= frontend/static/icons/master.png

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest

run: kill
	$(PYTHON) -m uvicorn main:app --host 0.0.0.0 --port $(PORT) --reload

admin:
	$(PYTHON) -m uvicorn admin.app:app --host 127.0.0.1 --port 8081 --reload

db:
	docker compose up -d db
	@echo "PostgreSQL running on localhost:5432 (flesh_pulse)"

db-stop:
	docker compose stop db

db-reset:
	docker compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS flesh_pulse;"
	docker compose exec db psql -U postgres -c "CREATE DATABASE flesh_pulse;"
	@echo "Database reset — restart the app to recreate tables"

reset: db-reset

trigger:
	curl -s -X POST http://localhost:$(PORT)/api/trigger-collection | $(PYTHON) -m json.tool

icons:
	./scripts/generate_icons.sh $(ICON_SRC)

# Free the port before starting (cross-platform best-effort)
kill:
	@-fuser -k $(PORT)/tcp 2>/dev/null || \
	  powershell -NoProfile -Command \
	    "$$p=(netstat -ano|Select-String ':$(PORT) .*LISTENING').ToString().Trim().Split()[-1]; \
	     if($$p){Stop-Process -Id $$p -Force -ErrorAction SilentlyContinue}" 2>/dev/null || true
