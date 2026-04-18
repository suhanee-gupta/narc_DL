import math
import numpy as np
from datetime import datetime, timezone
from config import CATEGORIES, ARCHETYPES, LOCATIONS, TIME_BUCKETS


def time_bucket(timestamp: str) -> str:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
                "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(timestamp.strip(), fmt)
            break
        except ValueError:
            continue
    else:
        return "evening"
    hour = dt.hour
    if hour < 6:   return "night"
    if hour < 12:  return "morning"
    if hour < 18:  return "afternoon"
    return "evening"


def _onehot(value, vocab: list) -> np.ndarray:
    vec = np.zeros(len(vocab), dtype=np.float32)
    if value in vocab:
        vec[vocab.index(value)] = 1.0
    return vec


def build(
    mood: dict,         # {happy, sad, angry, anxious, calm, curious} each 0-1
    archetype: str,
    location: str,
    timestamp: str,
    category: str,
    freshness: float,
    reranker_score: float = 0.0,
) -> np.ndarray:
    mood_vec      = np.array([mood.get(k, 0.0) for k in
                               ("happy","sad","angry","anxious","calm","curious")],
                              dtype=np.float32)
    archetype_vec = _onehot(archetype, ARCHETYPES)
    location_vec  = _onehot(location, LOCATIONS)
    time_vec      = _onehot(time_bucket(timestamp), TIME_BUCKETS)
    category_vec  = _onehot(category, CATEGORIES)
    freshness_vec = np.array([float(freshness)], dtype=np.float32)
    score_vec     = np.array([float(1.0 / (1.0 + math.exp(-reranker_score)))],
                              dtype=np.float32)

    ctx = np.concatenate([
        mood_vec,       # 6
        archetype_vec,  # 7
        location_vec,   # 3
        time_vec,       # 4
        category_vec,   # 24
        freshness_vec,  # 1
        score_vec,      # 1
    ])                  # = 46
    return ctx.astype(np.float64)
