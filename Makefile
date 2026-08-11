.PHONY: check check-web dev migrate seed-corpus

# Run all backend checks (ruff + pyright + pytest with testcontainers)
check:
	@cd api && .venv/bin/ruff check src/ tests/
	@cd api && .venv/bin/pyright src/
	@cd api && .venv/bin/pytest

# Run all frontend checks (oxlint + tsc + vite build)
check-web:
	@npx oxlint src/
	@npx tsc --noEmit
	@npx vite build

# Start the backend development server (loads secrets/.env if present)
dev:
	@if [ -f secrets/.env ]; then \
		set -a && . secrets/.env && set +a && cd api && uvicorn babynames_api.main:app --reload; \
	else \
		cd api && uvicorn babynames_api.main:app --reload; \
	fi

# Run database migrations (loads secrets/.env if present)
migrate:
	@if [ -f secrets/.env ]; then \
		set -a && . secrets/.env && set +a && cd api && alembic upgrade head; \
	else \
		cd api && alembic upgrade head; \
	fi

# Seed the name corpus into the database (loads secrets/.env if present)
seed-corpus:
	@if [ -f secrets/.env ]; then \
		set -a && . secrets/.env && set +a && cd api && python scripts/seed_corpus.py; \
	else \
		cd api && python scripts/seed_corpus.py; \
	fi
