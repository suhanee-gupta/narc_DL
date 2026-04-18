import json
import os
import numpy as np
from config import EMBED_DIM

PROFILES_DIR = "user_profiles"


def _path(user_id: str) -> str:
    return os.path.join(PROFILES_DIR, f"{user_id}.json")


def load(user_id: str) -> dict:
    p = _path(user_id)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            profile = json.load(f)
        # user_vec stored as list → back to ndarray
        profile["user_vec"] = np.array(profile["user_vec"], dtype=np.float32)
        return profile
    return init(user_id, "cold_start", "US")


def save(user_id: str, profile: dict) -> None:
    os.makedirs(PROFILES_DIR, exist_ok=True)
    out = {**profile, "user_vec": profile["user_vec"].tolist()}
    with open(_path(user_id), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def init(user_id: str, archetype: str = "cold_start", location: str = "US") -> dict:
    return {
        "user_id": user_id,
        "archetype": archetype,
        "location": location,
        "session_count": 0,
        "user_vec": np.zeros(EMBED_DIM, dtype=np.float32),
        "click_history": [],
    }
