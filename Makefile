.PHONY: check check-web dev migrate seed-corpus

# Creates api/.venv and installs the project (with dev deps) into it the first
# time any target needs it, so `make check` is genuinely zero-setup on a clean
# clone (quickstart.md: "no manual setup", FR-027/SC-008) rather than assuming
# .venv already exists. Re-runs pip install whenever pyproject.toml changes.
api/.venv/.installed: api/pyproject.toml
	@python3.12 -m venv api/.venv
	@api/.venv/bin/pip install --quiet --upgrade pip
	@api/.venv/bin/pip install --quiet -e "./api[dev]"
	@touch api/.venv/.installed

# Run all backend checks (ruff + pyright + pytest with testcontainers)
check: api/.venv/.installed
	@cd api && .venv/bin/ruff check src/ tests/
	@cd api && .venv/bin/pyright src/
	@cd api && .venv/bin/pytest

# Run all frontend checks (oxlint + tsc + vite build)
check-web:
	@npx oxlint src/
	@npx tsc --noEmit
	@npx vite build

# Start the backend development server (loads secrets/.env if present)
dev: api/.venv/.installed
	@if [ -f secrets/.env ]; then \
		set -a && . secrets/.env && set +a && cd api && .venv/bin/uvicorn babynames_api.main:app --reload; \
	else \
		cd api && .venv/bin/uvicorn babynames_api.main:app --reload; \
	fi

# Run database migrations (loads secrets/.env if present)
migrate: api/.venv/.installed
	@if [ -f secrets/.env ]; then \
		set -a && . secrets/.env && set +a && cd api && .venv/bin/alembic upgrade head; \
	else \
		cd api && .venv/bin/alembic upgrade head; \
	fi

# Seed the name corpus into the database (loads secrets/.env if present)
seed-corpus: api/.venv/.installed
	@if [ -f secrets/.env ]; then \
		set -a && . secrets/.env && set +a && cd api && .venv/bin/python scripts/seed_corpus.py; \
	else \
		cd api && .venv/bin/python scripts/seed_corpus.py; \
	fi
