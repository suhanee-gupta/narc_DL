"""
Cosine similarity pre-filter.
Pure function — no state, no side effects.

Selects the top-N articles closest to the user's context vector.
Cold-start fallback (zero user vector): sorts by freshness instead.
"""

import numpy as np
from user_maker import Article
from config import TOP_N_CANDIDATES


def cosine_rank(
    user_vec: np.ndarray,
    articles: list[Article],
    top_n: int = TOP_N_CANDIDATES,
) -> list[Article]:
    """
    Returns up to top_n articles sorted by descending cosine similarity
    to user_vec.  If user_vec is zero (cold start), sorts by freshness.
    """
    if not articles:
        return []

    norm = float(np.linalg.norm(user_vec))

    if norm < 1e-8:
        # cold start — no signal yet, surface freshest articles
        return sorted(articles, key=lambda a: a.freshness, reverse=True)[:top_n]

    user_unit = user_vec / norm

    # vectorized: (N, 256) @ (256,) → (N,)
    vecs = np.stack([a.vec for a in articles])          # (N, 256)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    scores = (vecs / norms) @ user_unit                 # (N,)

    k = min(top_n, len(articles))
    # argpartition is O(N) for the top-k cut, argsort only on the k winners
    top_idx = np.argpartition(scores, -k)[-k:]
    top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]

    return [articles[i] for i in top_idx]
