FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Dependencies resolve from pyproject.toml alone, so this layer is only rebuilt
# when the dependency set changes — not on every source edit.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Migrations and the corpus seeder ship with the image so the same artifact can
# apply schema and load names, even though the runbook drives both from the
# operator's machine (api/DEPLOY.md).
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts

EXPOSE 8000

# The daily keepalive job (api/DEPLOY.md step 7) runs this same image with
# `python -m babynames_api.keepalive` as its command instead.
CMD ["uvicorn", "babynames_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
