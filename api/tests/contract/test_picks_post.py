"""
Contract test: POST /v1/picks upserts on (account_id, slot, name_id),
keeps the later decidedAt on a repeated or overlapping batch,
and accepts picks for names outside the swiper's current block.
"""


def test_picks_upsert_idempotent(client, auth_headers, test_account, name_ids):
    """
    Upsert on (account_id, slot, name_id) — replaying the same batch
    or sending overlapping batches converges to the same state.
    """
    picks = [
        {
            "slot": 0,
            "name": "Emma",
            "verdict": "keep",
            "decidedAt": "2026-08-09T10:00:00Z",
        },
        {
            "slot": 0,
            "name": "Olivia",
            "verdict": "no",
            "decidedAt": "2026-08-09T10:01:00Z",
        },
    ]

    # First submission
    resp1 = client.post("/v1/picks", json={"picks": picks}, headers=auth_headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["accepted"] == 2

    # Replay the same batch — should be idempotent
    resp2 = client.post("/v1/picks", json={"picks": picks}, headers=auth_headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    # Still accepted, but no new rows created
    assert data2["accepted"] == 2

    # Verify state via GET /v1/state
    state = client.get("/v1/state", headers=auth_headers).json()
    assert len(state["picks"]) == 2
    assert any(p["name"] == "Emma" and p["verdict"] == "keep" for p in state["picks"])
    assert any(p["name"] == "Olivia" and p["verdict"] == "no" for p in state["picks"])


def test_picks_last_write_wins_on_decided_at(client, auth_headers, test_account, name_ids):
    """
    When the same (account, slot, name) is submitted multiple times,
    the row with the later decidedAt wins.
    """
    # First pick: keep, early timestamp
    picks1 = [
        {
            "slot": 0,
            "name": "Sophia",
            "verdict": "keep",
            "decidedAt": "2026-08-09T10:00:00Z",
        }
    ]
    resp1 = client.post("/v1/picks", json={"picks": picks1}, headers=auth_headers)
    assert resp1.status_code == 200

    # Second pick: no, later timestamp — should overwrite
    picks2 = [
        {
            "slot": 0,
            "name": "Sophia",
            "verdict": "no",
            "decidedAt": "2026-08-09T10:05:00Z",
        }
    ]
    resp2 = client.post("/v1/picks", json={"picks": picks2}, headers=auth_headers)
    assert resp2.status_code == 200

    # Verify the later verdict won
    state = client.get("/v1/state", headers=auth_headers).json()
    sophia_pick = next((p for p in state["picks"] if p["name"] == "Sophia"), None)
    assert sophia_pick is not None
    assert sophia_pick["verdict"] == "no"
    assert sophia_pick["decidedAt"] == "2026-08-09T10:05:00.000Z"


def test_picks_earlier_decided_at_does_not_overwrite(client, auth_headers, test_account, name_ids):
    """
    If an earlier decidedAt arrives after a later one (out-of-order sync),
    it should not overwrite the newer pick.
    """
    # First: later timestamp
    picks_later = [
        {
            "slot": 0,
            "name": "Ava",
            "verdict": "keep",
            "decidedAt": "2026-08-09T10:10:00Z",
        }
    ]
    resp1 = client.post(
        "/v1/picks", json={"picks": picks_later}, headers=auth_headers
    )
    assert resp1.status_code == 200

    # Second: earlier timestamp (out-of-order)
    picks_earlier = [
        {
            "slot": 0,
            "name": "Ava",
            "verdict": "no",
            "decidedAt": "2026-08-09T10:00:00Z",
        }
    ]
    resp2 = client.post(
        "/v1/picks", json={"picks": picks_earlier}, headers=auth_headers
    )
    assert resp2.status_code == 200

    # Verify the later verdict is still there
    state = client.get("/v1/state", headers=auth_headers).json()
    ava_pick = next((p for p in state["picks"] if p["name"] == "Ava"), None)
    assert ava_pick is not None
    assert ava_pick["verdict"] == "keep"
    assert ava_pick["decidedAt"] == "2026-08-09T10:10:00.000Z"


def test_picks_accepts_names_outside_current_block(client, auth_headers, test_account, name_ids):
    """
    Accept picks for names not in the swiper's current block,
    so a device that fell behind can still flush.
    """
    # Submit a pick for a name without first requesting it via /v1/deck/next
    picks = [
        {
            "slot": 0,
            "name": "Isabella",
            "verdict": "keep",
            "decidedAt": "2026-08-09T10:00:00Z",
        }
    ]
    resp = client.post("/v1/picks", json={"picks": picks}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 1

    # Verify it's stored
    state = client.get("/v1/state", headers=auth_headers).json()
    assert any(p["name"] == "Isabella" and p["verdict"] == "keep" for p in state["picks"])


def test_picks_returns_updated_positions(client, auth_headers, test_account, name_ids):
    """
    The response includes recomputed swiper positions so the client
    doesn't have to guess whether its local position survived the merge.
    """
    # Submit picks for slot 0
    picks = [
        {
            "slot": 0,
            "name": "Mia",
            "verdict": "keep",
            "decidedAt": "2026-08-09T10:00:00Z",
        },
        {
            "slot": 0,
            "name": "Charlotte",
            "verdict": "no",
            "decidedAt": "2026-08-09T10:01:00Z",
        },
    ]
    resp = client.post("/v1/picks", json={"picks": picks}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "swipers" in data
    assert isinstance(data["swipers"], list)
    assert any(s["slot"] == 0 for s in data["swipers"])


def test_picks_batch_with_repeated_name_keeps_latest(
    client, auth_headers, test_account, name_ids
):
    """
    One batch can hold the same name twice for the same slot — swipe, undo,
    swipe again all land in the outbox — and the later decidedAt wins.
    """
    picks = [
        {
            "slot": 0,
            "name": "Wren",
            "verdict": "keep",
            "decidedAt": "2026-08-09T10:00:00Z",
        },
        {
            "slot": 0,
            "name": "Wren",
            "verdict": "no",
            "decidedAt": "2026-08-09T10:02:00Z",
        },
    ]

    resp = client.post("/v1/picks", json={"picks": picks}, headers=auth_headers)
    assert resp.status_code == 200
    # Both entries are acknowledged so the client can clear them from its outbox
    assert resp.json()["accepted"] == 2

    state = client.get("/v1/state", headers=auth_headers).json()
    wren_picks = [p for p in state["picks"] if p["name"] == "Wren"]
    assert len(wren_picks) == 1
    assert wren_picks[0]["verdict"] == "no"
    assert wren_picks[0]["decidedAt"] == "2026-08-09T10:02:00.000Z"


def test_picks_batch_size_limit(client, auth_headers, test_account):
    """
    Batches are capped (suggested 500) so a long offline session
    flushes in several requests rather than one that might time out.
    """
    # Submit 501 picks — should be rejected or truncated
    picks = [
        {
            "slot": 0,
            "name": f"Name{i}",
            "verdict": "keep" if i % 2 == 0 else "no",
            "decidedAt": f"2026-08-09T10:{i % 60:02d}:00Z",
        }
        for i in range(501)
    ]
    resp = client.post("/v1/picks", json={"picks": picks}, headers=auth_headers)

    # Either 400 (rejected) or 200 with capped acceptance
    if resp.status_code == 400:
        error = resp.json()
        assert "error" in error
    else:
        assert resp.status_code == 200
        data = resp.json()
        # Should cap at 500
        assert data["accepted"] <= 500


def test_picks_different_slots_are_independent(client, auth_headers, test_account, name_ids):
    """
    Picks for different slots (swipers) are independent and can overlap
    on the same name without conflict.
    """
    picks = [
        {
            "slot": 0,
            "name": "Amelia",
            "verdict": "keep",
            "decidedAt": "2026-08-09T10:00:00Z",
        },
        {
            "slot": 1,
            "name": "Amelia",
            "verdict": "no",
            "decidedAt": "2026-08-09T10:01:00Z",
        },
    ]
    resp = client.post("/v1/picks", json={"picks": picks}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 2

    # Verify both picks exist
    state = client.get("/v1/state", headers=auth_headers).json()
    amelia_picks = [p for p in state["picks"] if p["name"] == "Amelia"]
    assert len(amelia_picks) == 2
    assert any(p["slot"] == 0 and p["verdict"] == "keep" for p in amelia_picks)
    assert any(p["slot"] == 1 and p["verdict"] == "no" for p in amelia_picks)
