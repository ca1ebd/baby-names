"""
T053: Integration test for deck exhaustion.

Requesting past the end of the corpus for a filter returns exhausted: true
with a short/empty block rather than repeating or silently emptying (FR-017).
"""

from fastapi.testclient import TestClient


def test_deck_exhaustion_returns_true(client: TestClient, db_session, make_account):
    """
    Requesting past the corpus end sets exhausted: true.
    """
    _, headers = make_account(deck_seed=12345, gender_filter="girl")

    # The real girl corpus has 39,749 names (plan.md); the test corpus is much
    # smaller. Request in large chunks to reach the end either way.
    total_received = 0
    exhausted = False

    for _ in range(250):  # 250 * 200 = 50,000 max requests
        response = client.post(
            "/v1/deck/next",
            json={"slot": 0, "count": 200},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()

        total_received += len(data["block"])

        if data["exhausted"]:
            exhausted = True
            # When exhausted, the block should be short or empty
            assert len(data["block"]) < 200, (
                "Exhausted response should have a short/empty block"
            )
            break

    assert exhausted, "Should eventually exhaust the corpus"
    assert total_received <= 39749, f"Received {total_received} names, expected ≤39,749"


def test_exhausted_does_not_repeat_names(client: TestClient, db_session, make_account):
    """
    After exhaustion, requesting more names does not repeat earlier names.
    """
    _, headers = make_account(deck_seed=54321, gender_filter="boy")

    seen_names = set()

    # Request until exhausted
    for _ in range(200):
        response = client.post(
            "/v1/deck/next",
            json={"slot": 0, "count": 200},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()

        for card in data["block"]:
            name = card["name"]
            assert name not in seen_names, f"Name '{name}' was repeated"
            seen_names.add(name)

        if data["exhausted"]:
            # Try requesting more after exhaustion
            response2 = client.post(
                "/v1/deck/next",
                json={"slot": 0, "count": 100},
                headers=headers,
            )
            assert response2.status_code == 200
            data2 = response2.json()

            # Should still be exhausted and return empty block
            assert data2["exhausted"] is True
            assert len(data2["block"]) == 0, (
                "After exhaustion, further requests should return empty blocks"
            )
            break
