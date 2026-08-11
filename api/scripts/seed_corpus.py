#!/usr/bin/env python3
"""Seed the name corpus into the `names` table.

Reads `babynames_api/corpus/names.json`, the artifact
`scripts/build-name-corpus.mjs` generates alongside the client's
`src/lib/nameCorpus.ts` from one curation pass over the SSA archive. The
service deliberately reads its own copy rather than parsing the TypeScript
module: that module is deleted once the client stops bundling the corpus, and
the seeding path has to outlive it.

Idempotent. Re-running inserts only names the table is missing and leaves
existing rows alone; a re-run against an already-seeded database is a no-op.
If an existing row disagrees with the JSON about gender, rank, or core
membership, the script reports it and exits non-zero rather than rewriting it —
`picks.name_id` and `served_order.name_id` point at these rows, so re-ranking an
already-served corpus is a migration, not a seed.
"""

from __future__ import annotations

import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from babynames_api.config import settings  # noqa: E402
from babynames_api.models.name import Name  # noqa: E402

# Resolved through the package rather than by walking up from this file, so the
# script works the same from a checkout and from inside the container image,
# where `scripts/` and the installed package do not share a parent.
CORPUS_PATH = Path(str(resources.files("babynames_api") / "corpus" / "names.json"))

# Rows per INSERT. The corpus is ~64k names; one statement per name is slow
# enough to be annoying over a hosted connection, and one statement for all of
# them overruns the parameter limit.
BATCH_SIZE = 1000


def load_corpus(path: Path) -> list[dict[str, Any]]:
    """Flatten the generated corpus into `names` rows.

    Array index is the popularity rank within a gender, and the first
    `<gender>CoreSize` entries are the core the deck deals first — the same
    contract the client's corpus module carries.
    """
    if not path.exists():
        sys.exit(
            f"Corpus artifact not found at {path}\n"
            f"Generate it with `npm run corpus:build` from the repository root."
        )

    data = json.loads(path.read_text())
    rows: list[dict[str, Any]] = []
    for gender in ("girl", "boy"):
        names = data[gender]
        core_size = data[f"{gender}CoreSize"]
        for rank, name in enumerate(names):
            rows.append(
                {
                    "name": name,
                    "gender": gender,
                    "rank": rank,
                    "is_core": rank < core_size,
                }
            )

    print(
        f"Loaded {len(data['girl'])} girl ({data['girlCoreSize']} core) "
        f"and {len(data['boy'])} boy ({data['boyCoreSize']} core) names "
        f"from {path.name} (source: {data['source']})"
    )
    return rows


def seed_corpus() -> None:
    rows = load_corpus(CORPUS_PATH)

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session = sessionmaker(bind=engine)()

    try:
        before = session.scalar(select(func.count()).select_from(Name)) or 0

        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start : start + BATCH_SIZE]
            session.execute(
                insert(Name).values(batch).on_conflict_do_nothing(index_elements=["name"])
            )
        session.commit()

        after = session.scalar(select(func.count()).select_from(Name)) or 0
        inserted = after - before
        if inserted:
            print(f"Inserted {inserted} names ({before} already present, {after} total)")
        else:
            print(f"No new names — corpus already seeded ({after} total)")

        drift = check_drift(session, rows)
        if drift:
            print(
                f"\n{len(drift)} existing row(s) disagree with the corpus artifact. "
                "Not rewriting them — picks and served_order reference these ids, "
                "so re-ranking a served corpus needs a deliberate migration.",
                file=sys.stderr,
            )
            for line in drift[:10]:
                print(f"  {line}", file=sys.stderr)
            if len(drift) > 10:
                print(f"  … and {len(drift) - 10} more", file=sys.stderr)
            sys.exit(1)

        print("Corpus is consistent with the generated artifact.")

    except SystemExit:
        raise
    except Exception as exc:
        session.rollback()
        sys.exit(f"Error seeding corpus: {exc}")
    finally:
        session.close()


def check_drift(session: Any, rows: list[dict[str, Any]]) -> list[str]:
    """Report rows whose gender/rank/core membership differs from the artifact."""
    expected = {row["name"]: row for row in rows}
    drift: list[str] = []

    for name, gender, rank, is_core in session.execute(
        select(Name.name, Name.gender, Name.rank, Name.is_core)
    ):
        want = expected.pop(name, None)
        if want is None:
            drift.append(f"{name!r}: in the database but not in the corpus artifact")
        elif (gender, rank, is_core) != (want["gender"], want["rank"], want["is_core"]):
            drift.append(
                f"{name!r}: database has ({gender}, rank {rank}, core={is_core}), "
                f"artifact has ({want['gender']}, rank {want['rank']}, "
                f"core={want['is_core']})"
            )

    for name in list(expected)[:10]:
        drift.append(f"{name!r}: in the corpus artifact but missing from the database")

    return drift


if __name__ == "__main__":
    seed_corpus()
