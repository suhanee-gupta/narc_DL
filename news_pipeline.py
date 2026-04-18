import json
import pickle
import math
import numpy as np
from datetime import datetime, timezone
from typing import Optional
from user_maker import Article
from config import FRESHNESS_HALF_LIFE_HOURS


def _parse_date(date_str: str) -> Optional[datetime]:
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _freshness(date_str: str) -> float:
    dt = _parse_date(date_str)
    if dt is None:
        return 0.1
    now = datetime.now(timezone.utc)
    age_hours = max((now - dt).total_seconds() / 3600.0, 0.0)
    return float(math.exp(-age_hours / FRESHNESS_HALF_LIFE_HOURS))


class NewsPipeline:
    def __init__(self, json_path: str = "google_news_5000.json",
                 embeddings_pkl: str = "title_embeddings.pkl"):
        self.json_path = json_path
        self.embeddings_pkl = embeddings_pkl
        self._articles: list[Article] = []
        self._by_id: dict[str, Article] = {}
        self._embeddings: np.ndarray = np.empty(0)  # shape (N, 768)
        self._idx_by_id: dict[str, int] = {}

    def load(self) -> None:
        with open(self.json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        with open(self.embeddings_pkl, "rb") as f:
            self._embeddings = pickle.load(f).astype(np.float32)  # (4860, 768)

        self._articles = []
        self._by_id = {}
        self._idx_by_id = {}

        for i, row in enumerate(raw):
            sid = str(row["story_id"])
            article = Article(
                id=sid,
                category=row.get("category", ""),
                subcategory=(row.get("tags") or [""])[0],
                title=row.get("title", ""),
                vec=np.zeros(1, dtype=np.float32),
                freshness=_freshness(row.get("published_date", "")),
                summary=row.get("summary", ""),
            )
            self._articles.append(article)
            self._by_id[sid] = article
            self._idx_by_id[sid] = i

        print(f"NewsPipeline: loaded {len(self._articles)} articles.")

    def get_articles(self) -> list[Article]:
        return self._articles

    def get_article(self, story_id: str) -> Optional[Article]:
        return self._by_id.get(str(story_id))

    def get_embedding(self, story_id: str) -> Optional[np.ndarray]:
        idx = self._idx_by_id.get(str(story_id))
        if idx is None:
            return None
        return self._embeddings[idx]

    def get_all_embeddings(self) -> np.ndarray:
        """Returns (N, 768) matrix in same order as get_articles()."""
        return self._embeddings
