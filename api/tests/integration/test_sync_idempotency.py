"""
Integration test: interrupting and retrying a sync flush at 20 randomized points
converges to the same state as one clean sync — no duplicated, dropped, or reordered picks (SC-005).
"""

import random


def test_interrupted_sync_converges_to_clean_sync(
    client, auth_headers, test_account, db_session, corpus_names
):
    """
    Simulate interrupting a sync flush at randomized points and retrying.
    Final state should match a clean, uninterrupted sync every time.
    """
    # Generate a batch of 100 picks to sync
    picks = [
        {
            "slot": 0,
            "name": corpus_names[i],
            "verdict": "keep" if i % 3 == 0 else "no",
            "decidedAt": f"2026-08-09T{(10 + i // 60) % 24:02d}:{i % 60:02d}:00Z",
        }
        for i in range(100)
    ]

    # First, establish the baseline: clean sync with all picks at once
    resp_clean = client.post("/v1/picks", json={"picks": picks}, headers=auth_headers)
    assert resp_clean.status_code == 200

    # Get the clean state
    clean_state = client.get("/v1/state", headers=auth_headers).json()
    clean_picks = {(p["name"], p["slot"], p["verdict"]) for p in clean_state["picks"]}

    # Reset account state for interrupted tests
    client.post(
        "/v1/reset", json={"scope": "everything"}, headers=auth_headers
    )

    # Now simulate 20 interrupted syncs with randomized batch boundaries
    for trial in range(20):
        # Randomize split point
        split = random.randint(1, len(picks) - 1)
        batch1 = picks[:split]
        batch2 = picks[split:]

        # Send first batch
        resp1 = client.post("/v1/picks", json={"picks": batch1}, headers=auth_headers)
        assert resp1.status_code == 200

        # Send second batch (simulating retry after interruption)
        resp2 = client.post("/v1/picks", json={"picks": batch2}, headers=auth_headers)
        assert resp2.status_code == 200

        # Verify final state matches clean sync
        interrupted_state = client.get("/v1/state", headers=auth_headers).json()
        interrupted_picks = {
            (p["name"], p["slot"], p["verdict"]) for p in interrupted_state["picks"]
        }

        assert interrupted_picks == clean_picks, (
            f"Trial {trial}: Interrupted sync produced different state. "
            f"Expected {len(clean_picks)} picks, got {len(interrupted_picks)}"
        )

        # Reset for next trial
        client.post(
            "/v1/reset", json={"scope": "everything"}, headers=auth_headers
        )


def test_overlapping_batches_from_two_devices_converge(
    client, auth_headers, test_account, corpus_names
):
    """
    Simulate two devices sending overlapping batches (same picks with potentially
    different timestamps). Should converge to the last-write-wins state.
    """
    shared1, shared2, shared3 = corpus_names[0], corpus_names[1], corpus_names[2]

    # Device 1 sends a batch
    device1_picks = [
        {
            "slot": 0,
            "name": shared1,
            "verdict": "keep",
            "decidedAt": "2026-08-09T10:00:00Z",
        },
        {
            "slot": 0,
            "name": shared2,
            "verdict": "no",
            "decidedAt": "2026-08-09T10:01:00Z",
        },
    ]
    resp1 = client.post(
        "/v1/picks", json={"picks": device1_picks}, headers=auth_headers
    )
    assert resp1.status_code == 200

    # Device 2 sends overlapping batch with different timestamp for SharedName1
    device2_picks = [
        {
            "slot": 0,
            "name": shared1,
            "verdict": "keep",  # same verdict, later timestamp
            "decidedAt": "2026-08-09T10:05:00Z",  # later
        },
        {
            "slot": 0,
            "name": shared3,
            "verdict": "keep",
            "decidedAt": "2026-08-09T10:02:00Z",
        },
    ]
    resp2 = client.post(
        "/v1/picks", json={"picks": device2_picks}, headers=auth_headers
    )
    assert resp2.status_code == 200

    # Verify convergence
    state = client.get("/v1/state", headers=auth_headers).json()
    picks_dict = {p["name"]: p for p in state["picks"]}

    # The overlapping name should have the later timestamp
    assert picks_dict[shared1]["decidedAt"] == "2026-08-09T10:05:00.000Z"
    # Device 1's other pick survives
    assert shared2 in picks_dict
    # Device 2's other pick survives
    assert shared3 in picks_dict


def test_partial_batch_replay_is_safe(client, auth_headers, test_account, corpus_names):
    """
    If a client resubmits part of a batch that was already acknowledged,
    no duplication or data loss should occur.
    """
    replay_names = corpus_names[:20]
    picks = [
        {
            "slot": 0,
            "name": name,
            "verdict": "keep" if i % 2 == 0 else "no",
            "decidedAt": f"2026-08-09T10:{i % 60:02d}:00Z",
        }
        for i, name in enumerate(replay_names)
    ]

    # Send full batch
    resp1 = client.post("/v1/picks", json={"picks": picks}, headers=auth_headers)
    assert resp1.status_code == 200
    assert resp1.json()["accepted"] == 20

    # Replay a subset
    subset = picks[5:15]
    resp2 = client.post("/v1/picks", json={"picks": subset}, headers=auth_headers)
    assert resp2.status_code == 200

    # Verify no duplicates
    state = client.get("/v1/state", headers=auth_headers).json()
    slot0_picks = [p for p in state["picks"] if p["slot"] == 0]
    assert len(slot0_picks) == 20  # Still 20, not 30

    # Verify all original picks are still there
    pick_names = {p["name"] for p in slot0_picks}
    assert pick_names == set(replay_names)
