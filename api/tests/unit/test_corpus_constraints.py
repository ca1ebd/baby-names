"""FR-016: girl and boy name sets must share zero spellings. Picks are keyed
by name (spec 001), so a collision would let a pick made under one gender
silently affect the other. Enforced at the schema level by `names.name`
being globally unique (not per-gender) — this test proves that constraint
actually rejects a cross-gender duplicate rather than just asserting the
column exists."""

from sqlalchemy.exc import IntegrityError

from babynames_api.models.name import Name


def test_duplicate_name_across_genders_is_rejected(db_session):
    db_session.add(Name(name="ZZZ_Overlap_Test", gender="girl", rank=999999, is_core=False))
    db_session.commit()

    db_session.add(Name(name="ZZZ_Overlap_Test", gender="boy", rank=999999, is_core=False))
    try:
        db_session.commit()
        raise AssertionError("expected IntegrityError for a duplicate name across genders")
    except IntegrityError:
        db_session.rollback()
