# ==========================================================
# TAG-BASED NEWS RECOMMENDER — DEPLOYMENT READY
# ==========================================================

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional
from app.core.interfaces import BaseRetriever, ContextObject
from app.core.config import settings

import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# ==========================================================
# CONFIG
# ==========================================================

# ==========================================================
# CONTEXT OBJECT

# ==========================================================
# GLOBALS — loaded once at startup
# ==========================================================


# ==========================================================
# INTERNALS
# ==========================================================







# ==========================================================
# PUBLIC API
# ==========================================================
class TransformerRetriever(BaseRetriever):
    def __init__(self, df: pd.DataFrame, model, tokenizer):
        self._df = df
        self._model = model
        self._tokenizer = tokenizer
        self._model.to(settings.DEVICE)
        self._model.eval()

    def retrieve(self, context: ContextObject) -> list[str]:
        """
        Returns a ranked list of top-k story_id strings
        not present in context.history.
        """
        pref_cat     = self._plurality_category(context.history)
        query        = self._build_query(pref_cat, context.history)
        candidate_df = self._df[~self._df["story_id_str"].isin(context.history)].copy()

        candidate_df["score"] = self._score_pairs(query, candidate_df["article_text"].tolist())
        candidate_df = candidate_df.sort_values("score", ascending=False)

        return candidate_df.head(context.top_k)["story_id_str"].tolist()
    

    def _plurality_category(self, history_ids: list[str]) -> str:
        read_df = self._df[self._df["story_id_str"].isin(history_ids)]
        if read_df.empty:
            return self._df["category"].mode().iloc[0]
        return Counter(read_df["category"].tolist()).most_common(1)[0][0]
    

    def _build_query(self, pref_cat: str, history_ids: list[str], max_titles: int = 5) -> str:
        history_df   = self._df[self._df["story_id_str"].isin(history_ids)]
        cat_titles   = history_df[history_df["category"] == pref_cat]["title"].tolist()
        other_titles = history_df[history_df["category"] != pref_cat]["title"].tolist()
        selected     = (cat_titles + other_titles)[:max_titles]
        return f"{pref_cat} news. Examples: {' | '.join(selected)}"
        

    @torch.no_grad()
    def _score_pairs(self, query: str, docs: list[str], batch_size: int = 8) -> list[float]:
        scores = []
        for i in range(0, len(docs), batch_size):
            batch  = docs[i : i + batch_size]
            inputs = self._tokenizer(
                [[query, d] for d in batch],
                padding=True, truncation=True,
                max_length=512, return_tensors="pt"
            )
            inputs = {k: v.to(settings.DEVICE) for k, v in inputs.items()}
            scores.extend(self._model(**inputs).logits.view(-1).cpu().tolist())
        return scores
