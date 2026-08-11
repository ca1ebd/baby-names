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

# Run all backend checks (ruff + pyright + pytest with testcontainers).
# Runs all three even if an earlier one fails, so a broken type and a broken
# test are both visible in one pass instead of the second being hidden until
# the first is fixed and check is re-run (T078).
check: api/.venv/.installed
	@cd api && \
	.venv/bin/ruff check src/ tests/; RUFF=$$?; \
	.venv/bin/pyright src/; PYRIGHT=$$?; \
	.venv/bin/pytest; PYTEST=$$?; \
	if [ $$RUFF -ne 0 ] || [ $$PYRIGHT -ne 0 ] || [ $$PYTEST -ne 0 ]; then \
		echo ""; \
		echo "make check FAILED:"; \
		[ $$RUFF -ne 0 ] && echo "  - ruff (lint)"; \
		[ $$PYRIGHT -ne 0 ] && echo "  - pyright (types)"; \
		[ $$PYTEST -ne 0 ] && echo "  - pytest (tests)"; \
		exit 1; \
	fi

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
