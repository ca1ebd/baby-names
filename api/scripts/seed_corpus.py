#!/usr/bin/env python3
"""
Seed the name corpus into the database from the TypeScript corpus file.
Idempotent: can be run multiple times safely.
"""
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Add parent to path so we can import from babynames_api
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from babynames_api.config import settings
from babynames_api.db import Base
from babynames_api.models.name import Name


def parse_corpus_file(corpus_path: Path) -> tuple[list[str], list[str], int, int]:
    """Parse the TypeScript corpus file and extract names"""
    content = corpus_path.read_text()

    # Extract core sizes
    girl_core_match = re.search(r'GIRL_CORE_SIZE\s*=\s*(\d+)', content)
    boy_core_match = re.search(r'BOY_CORE_SIZE\s*=\s*(\d+)', content)

    if not girl_core_match or not boy_core_match:
        raise ValueError("Could not find GIRL_CORE_SIZE or BOY_CORE_SIZE")

    girl_core_size = int(girl_core_match.group(1))
    boy_core_size = int(boy_core_match.group(1))

    # Extract girl corpus
    girl_match = re.search(r'GIRL_CORPUS[^"]*"([^"]+)"', content)
    if not girl_match:
        raise ValueError("Could not find GIRL_CORPUS")

    girl_names = [name.strip() for name in girl_match.group(1).split(',') if name.strip()]

    # Extract boy corpus
    boy_match = re.search(r'BOY_CORPUS[^"]*"([^"]+)"', content)
    if not boy_match:
        raise ValueError("Could not find BOY_CORPUS")

    boy_names = [name.strip() for name in boy_match.group(1).split(',') if name.strip()]

    return girl_names, boy_names, girl_core_size, boy_core_size


def seed_corpus():
    """Seed the corpus into the database"""
    # Find the corpus file
    repo_root = Path(__file__).resolve().parents[2]
    corpus_path = repo_root / "src" / "lib" / "nameCorpus.ts"

    if not corpus_path.exists():
        print(f"Error: Corpus file not found at {corpus_path}")
        sys.exit(1)

    print(f"Parsing corpus from {corpus_path}...")
    girl_names, boy_names, girl_core_size, boy_core_size = parse_corpus_file(corpus_path)

    print(f"Found {len(girl_names)} girl names ({girl_core_size} core)")
    print(f"Found {len(boy_names)} boy names ({boy_core_size} core)")

    # Connect to database
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        # Check if corpus is already seeded
        existing_count = session.scalar(select(Name).limit(1))
        if existing_count:
            print("Corpus already seeded. Skipping.")
            return

        print("Seeding corpus into database...")

        # Insert girl names
        for rank, name in enumerate(girl_names):
            is_core = rank < girl_core_size
            name_obj = Name(
                name=name,
                gender="girl",
                rank=rank,
                is_core=is_core
            )
            session.add(name_obj)

        # Insert boy names
        for rank, name in enumerate(boy_names):
            is_core = rank < boy_core_size
            name_obj = Name(
                name=name,
                gender="boy",
                rank=rank,
                is_core=is_core
            )
            session.add(name_obj)

        session.commit()
        print(f"Successfully seeded {len(girl_names) + len(boy_names)} names")

    except Exception as e:
        session.rollback()
        print(f"Error seeding corpus: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    seed_corpus()
