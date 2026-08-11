"""
T049: Unit test for the weighted shuffle deck algorithm.

The Python weightedShuffle port must match the frontend's float64 semantics exactly:
- ~71.6% of a 7,457-entry core underflows to key 0.0 first at rank 230
- dealt order is strict rank past ~position 2,118
- median rank of the first 20 cards is 180-235 (research §5)
"""

from babynames_api.deck import weighted_shuffle


def test_weighted_shuffle_underflow_at_rank_230():
    """
    First underflow (key = 0.0) occurs at rank 230 in a 7,457-entry core.

    This is a known float64 artifact from u^(rank+1) where u is in [0,1).
    The Python port must reproduce it faithfully.
    """
    # Use the same seed as the frontend
    seed = 20260730
    core_size = 7457

    # Create a test corpus with indices as names
    test_corpus = [f"name_{i}" for i in range(core_size)]

    # Run the weighted shuffle
    shuffled = weighted_shuffle(test_corpus, seed)

    # The algorithm assigns key = u^(rank+1), and for ranks starting around 230,
    # this underflows to 0.0 in float64. We can't easily inspect the keys after
    # the sort, but we know the consequence: ~71.6% of the core (5,341 names)
    # end up with key=0.0 and are then sorted by strict rank among themselves.

    # So after position ~2,118 (28.4% of 7,457), the output should be strict rank.
    # Check that positions 5000-5010 are in ascending rank order:
    for i in range(5000, 5009):
        current_rank = int(shuffled[i].split("_")[1])
        next_rank = int(shuffled[i + 1].split("_")[1])
        # In the strict-rank region, each entry should have rank > previous
        assert next_rank > current_rank, (
            f"Expected strict rank ordering past position 2118, "
            f"but position {i} has rank {current_rank} "
            f"followed by rank {next_rank}"
        )


def test_weighted_shuffle_median_rank_of_first_20():
    """
    The median rank of the first 20 cards should be 180-235.

    This validates the weighted sampling is working: not a flat shuffle
    (which would give median ~3,729) and not strict rank (median 10).
    """
    seed = 20260730
    core_size = 7457
    test_corpus = [f"name_{i}" for i in range(core_size)]

    shuffled = weighted_shuffle(test_corpus, seed)

    # Extract the ranks of the first 20 cards
    first_20_ranks = [int(shuffled[i].split("_")[1]) for i in range(20)]
    first_20_ranks.sort()

    # Median of 20 items is the average of the 10th and 11th
    median = (first_20_ranks[9] + first_20_ranks[10]) / 2

    assert 180 <= median <= 235, (
        f"Median rank of first 20 cards is {median}, expected 180-235. "
        f"First 20 ranks: {first_20_ranks[:20]}"
    )


def test_weighted_shuffle_deterministic():
    """
    The same seed produces the same shuffle every time.
    """
    seed = 20260730
    test_corpus = [f"name_{i}" for i in range(100)]

    shuffle1 = weighted_shuffle(test_corpus, seed)
    shuffle2 = weighted_shuffle(test_corpus, seed)

    assert shuffle1 == shuffle2, "Same seed should produce identical shuffle"


def test_weighted_shuffle_different_seeds_differ():
    """
    Different seeds produce different shuffles.
    """
    test_corpus = [f"name_{i}" for i in range(100)]

    shuffle1 = weighted_shuffle(test_corpus, 20260730)
    shuffle2 = weighted_shuffle(test_corpus, 20260731)

    assert shuffle1 != shuffle2, "Different seeds should produce different shuffles"


def test_weighted_shuffle_preserves_all_elements():
    """
    Shuffling doesn't lose or duplicate elements.
    """
    test_corpus = [f"name_{i}" for i in range(100)]
    shuffled = weighted_shuffle(test_corpus, 20260730)

    assert len(shuffled) == len(test_corpus)
    assert set(shuffled) == set(test_corpus)
