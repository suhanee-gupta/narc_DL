EMBED_DIM = 768
CONTEXT_DIM = 46

TOP_N_CANDIDATES = 50
TOP_K_RECS = 10
FAST_LOOP_ROUNDS = 50        # As requested: 50 fast loops per session
SLOW_LOOP_FLUSH_EVERY = 2    # As requested: 50 rounds / 2 = 25 flushes (approx 20)
RERANK_REFRESH_EVERY = 1     # Refresh more often in simulation to see the loop react
BANDIT_ALPHA = 0.2           # TRICK: Lower alpha = faster exploitation (quicker convergence)

SLOW_LOOP_INTERVAL_SEC = 3600
SLOW_LOOP_LR = 0.4               # aggressive slow loop update for demo
FAST_LOOP_USER_VEC_LR = 0.7      # user_vec shifts strongly after 2-3 interactions

FRESHNESS_HALF_LIFE_HOURS = 24.0

CATEGORIES = [
    "AI","Bitcoin","Business","Cricket","Crypto","Education","Elections",
    "Entertainment","Environment","Finance","Health","IPL","Inflation",
    "Markets","Movies","OpenAI","Politics","Science","Sports","Startups",
    "Technology","Tesla","War","World"
]

ARCHETYPES = [
    "cold_start","sports_fan","sci_tech","finance_biz",
    "wellness","world_watcher","foodie_lifestyle"
]

LOCATIONS = ["India", "US", "UK"]

TIME_BUCKETS = ["morning", "afternoon", "evening", "night"]

ARCHETYPE_CATEGORY_WEIGHTS = {
    "cold_start": {c: 1/24 for c in CATEGORIES},
    "sports_fan": {
        "Sports":0.30,"Cricket":0.25,"IPL":0.20,"Entertainment":0.05,
        **{c:0.01 for c in CATEGORIES if c not in {"Sports","Cricket","IPL","Entertainment"}}
    },
    "sci_tech": {
        "Technology":0.22,"AI":0.22,"Science":0.18,"OpenAI":0.12,"Startups":0.10,
        **{c:0.01 for c in CATEGORIES if c not in {"Technology","AI","Science","OpenAI","Startups"}}
    },
    "finance_biz": {
        "Finance":0.20,"Business":0.18,"Markets":0.15,"Inflation":0.10,
        "Bitcoin":0.08,"Crypto":0.07,"Tesla":0.06,"Startups":0.05,
        **{c:0.01 for c in CATEGORIES if c not in {"Finance","Business","Markets","Inflation","Bitcoin","Crypto","Tesla","Startups"}}
    },
    "wellness": {
        "Health":0.40,"Education":0.30,"Environment":0.20,
        **{c:0.01 for c in CATEGORIES if c not in {"Health","Education","Environment"}}
    },
    "world_watcher": {
        "World":0.28,"Politics":0.24,"Elections":0.20,"War":0.15,
        **{c:0.01 for c in CATEGORIES if c not in {"World","Politics","Elections","War"}}
    },
    "foodie_lifestyle": {
        "Entertainment":0.45,"Movies":0.40,
        **{c:0.01 for c in CATEGORIES if c not in {"Entertainment","Movies"}}
    },
}

# Normalize each archetype's weights to sum to 1
for _arch, _wts in ARCHETYPE_CATEGORY_WEIGHTS.items():
    _total = sum(_wts.values())
    ARCHETYPE_CATEGORY_WEIGHTS[_arch] = {k: v/_total for k, v in _wts.items()}

MOOD_MODIFIERS = {
    "anxious": {"deprioritize": ["War","Elections","Inflation"],    "boost": ["Health","Science"]},
    "angry":   {"deprioritize": ["Politics","Elections"],           "boost": ["Sports","Entertainment"]},
    "sad":     {"deprioritize": ["War","Elections"],                "boost": ["Entertainment","Movies"]},
    "curious": {"deprioritize": [],                                 "boost": ["AI","Science","Technology","World"]},
    "calm":    {"deprioritize": ["Entertainment","IPL"],            "boost": ["Finance","Science","World"]},
    "happy":   {"deprioritize": [],                                 "boost": []},
}
