from src.core.embeddings import compute_hashing_embedding_similarity


def test_hashing_embedding_similarity_is_higher_for_related_texts():
    similar = compute_hashing_embedding_similarity(
        "Liverpool transfer plan changes after late injury blow",
        "Liverpool transfer plan changes after injury concern before weekend match",
    )
    different = compute_hashing_embedding_similarity(
        "Liverpool transfer plan changes after late injury blow",
        "Tesla unveils a new battery manufacturing process for energy storage",
    )

    assert 0.0 <= different <= 1.0
    assert 0.0 <= similar <= 1.0
    assert similar > different
