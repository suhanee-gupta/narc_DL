"""
Reads news_vectors.pkl (produced by news_encoder.py) and news.tsv metadata.
Assembles Article objects. Does NOT call the encoder or touch raw embeddings.
"""

import pickle
from typing import Optional
import numpy as np

from user_maker import Article


class NewsPipeline:
    def __init__(self, news_tsv: str, news_vectors_pkl: str):
        self.news_tsv = news_tsv
        self.news_vectors_pkl = news_vectors_pkl
        self._store: dict[str, Article] = {}

    def load(self) -> None:
        """Load news_vectors.pkl and news.tsv, build the Article store."""
        with open(self.news_vectors_pkl, "rb") as f:
            vectors: dict[str, np.ndarray] = pickle.load(f)

        rows: list[list[str]] = []
        with open(self.news_tsv, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 4:
                    rows.append(parts)

        total = len(rows)
        self._store = {}

        for i, row in enumerate(rows):
            news_id = row[0]
            if news_id not in vectors:
                continue

            category = row[1].lower().strip()
            subcategory = row[2].lower().strip()
            title = row[3].strip()

            # Freshness proxy: earlier rows = more recent.
            # Swap to timestamp-based formula once published_at is available:
            #   freshness = 2 ** (- hours_since_published / FRESHNESS_HALF_LIFE_HOURS)
            freshness = float(1.0 - i / max(total - 1, 1))

            self._store[news_id] = Article(
                id=news_id,
                category=category,
                subcategory=subcategory,
                title=title,
                vec=vectors[news_id].astype(np.float32),
                freshness=freshness,
            )

        print(f"NewsPipeline loaded {len(self._store)} articles.")

    def get_articles(self) -> list[Article]:
        """All articles sorted freshest-first."""
        return sorted(self._store.values(), key=lambda a: a.freshness, reverse=True)

    def get_article(self, news_id: str) -> Optional[Article]:
        return self._store.get(news_id)
