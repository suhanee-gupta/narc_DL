import numpy as np
import json
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import random

# ── article schema ──────────────────────────────────────────────────────────
@dataclass
class Article:
    id: str
    category: str
    subcategory: str
    title: str
    vec: np.ndarray
    freshness: float
    summary: str = ""

# ── user policy (defines who this user is) ──────────────────────────────────
@dataclass
class UserPolicy:
    user_id: str
    
    # category preferences: weight per category, sums to 1
    category_weights: Dict[str, float]
    
    # behavioral traits
    curiosity: float        # 0-1. high = explores new categories
    patience: float         # 0-1. high = reads even if not perfect match
    recency_bias: float     # 0-1. high = strongly prefers fresh news
    position_bias: float    # 0-1. high = clicks top results regardless of relevance
    satiation_rate: float   # 0-1. high = gets bored of same category quickly
    
    # session traits
    session_length: int     # avg articles interacted with per session
    active_hours: List[int] # hours of day this user is active [8, 9, 12, 18]
    
    # mood model
    mood_volatility: float  # 0-1. high = mood shifts quickly within session

# ── session state (changes during session) ──────────────────────────────────
@dataclass
class SessionState:
    user_id: str
    current_mood: float = 0.5        # 0=distracted, 1=engaged
    category_counts: Dict[str, int] = field(default_factory=dict)
    interactions: List[Dict] = field(default_factory=list)
    step: int = 0

# ── action types ────────────────────────────────────────────────────────────
# click       : user opened the article
# skip        : user scrolled past quickly (saw headline, ignored)
# dwell_short : user opened, left in <15s (disappointed)
# dwell_long  : user opened, read fully (satisfied)
# share       : user shared (very positive signal)

ACTION_TYPES = ['click', 'skip', 'dwell_short', 'dwell_long', 'share']

# ────────────────────────────────────────────────────────────────────────────

class UserEngine:
    
    def __init__(self, policy: UserPolicy):
        self.policy = policy
    
    def start_session(self) -> SessionState:
        return SessionState(user_id=self.policy.user_id)
    
    def _relevance_score(self, article: Article, state: SessionState) -> float:
        """How relevant is this article to this user right now."""
        p = self.policy
        
        # base: category preference
        base = p.category_weights.get(article.category, 0.05)
        
        # recency factor
        recency = article.freshness * p.recency_bias + (1 - p.recency_bias) * 0.5
        
        # satiation: if user has seen too much of this category, reduce score
        cat_count = state.category_counts.get(article.category, 0)
        satiation = np.exp(-p.satiation_rate * cat_count)
        
        # curiosity: occasionally boosts a non-preferred category
        curiosity_boost = 0.0
        if random.random() < p.curiosity:
            if base < 0.2:  # non-preferred category
                curiosity_boost = 0.15
        
        # mood: engaged users interact more broadly
        mood_factor = 0.7 + 0.6 * state.current_mood
        
        score = base * recency * satiation * mood_factor + curiosity_boost
        return float(np.clip(score, 0.0, 1.0))
    
    def _position_adjusted_prob(
        self, 
        relevance: float, 
        position: int,
        state: SessionState
    ) -> float:
        """P(user notices this article at this position)."""
        # position decay: user attention drops as they scroll
        position_weight = np.exp(-self.policy.position_bias * position * 0.3)
        
        # patience: low patience users give up scrolling early
        patience_factor = np.exp(-position * (1 - self.policy.patience) * 0.2)
        
        p_notice = position_weight * patience_factor
        p_click_given_notice = relevance
        
        return float(p_notice * p_click_given_notice)
    
    def _decide_action(
        self, 
        article: Article, 
        relevance: float, 
        p_interact: float
    ) -> str:
        """Given user noticed and clicked, what specific action do they take."""
        
        if random.random() > p_interact:
            return 'skip'
        
        # they clicked — now decide depth of engagement
        # high relevance + high mood = dwell_long or share
        # low relevance = dwell_short (clicked but disappointed)
        
        r = relevance * (0.5 + 0.5 * self.policy.patience)
        
        roll = random.random()
        if roll < r * 0.15:
            return 'share'          # very positive, rare
        elif roll < r * 0.6:
            return 'dwell_long'     # read fully
        elif roll < r * 0.85:
            return 'click'          # opened, partial read
        else:
            return 'dwell_short'    # opened, bounced
    
    def _update_mood(self, action: str, state: SessionState) -> float:
        """Mood evolves based on whether user found what they wanted."""
        mood = state.current_mood
        v = self.policy.mood_volatility
        
        delta = {
            'share':       +0.3,
            'dwell_long':  +0.2,
            'click':       +0.05,
            'dwell_short': -0.15,
            'skip':        -0.05,
        }[action]
        
        new_mood = mood + v * delta + np.random.normal(0, 0.05)
        return float(np.clip(new_mood, 0.0, 1.0))
    
    def interact_with_feed(
        self, 
        ranked_articles: List[Article],
        state: SessionState
    ) -> Tuple[List[Dict], SessionState]:
        """
        Given a ranked list of articles, simulate user behavior.
        Returns list of interactions and updated session state.
        
        This is the function your RL environment calls.
        """
        interactions = []
        
        for position, article in enumerate(ranked_articles):
            
            # user has a session length limit
            if state.step >= self.policy.session_length:
                break
            
            relevance = self._relevance_score(article, state)
            p_interact = self._position_adjusted_prob(relevance, position, state)
            action = self._decide_action(article, relevance, p_interact)
            
            interaction = {
                'user_id':   self.policy.user_id,
                'article_id': article.id,
                'category':  article.category,
                'position':  position,
                'relevance': round(relevance, 3),
                'action':    action,
                'mood_before': round(state.current_mood, 3),
                'step':      state.step,
            }
            
            # update state
            state.current_mood = self._update_mood(action, state)
            state.category_counts[article.category] = (
                state.category_counts.get(article.category, 0) + 1
            )
            state.step += 1
            state.interactions.append(interaction)
            interactions.append(interaction)
        
        return interactions, state


# ── factory: generate 100 diverse users ─────────────────────────────────────

# Must match config.CATEGORIES exactly (case-sensitive)
CATEGORIES = [
    "AI", "Bitcoin", "Business", "Cricket", "Crypto", "Education", "Elections",
    "Entertainment", "Environment", "Finance", "Health", "IPL", "Inflation",
    "Markets", "Movies", "OpenAI", "Politics", "Science", "Sports", "Startups",
    "Technology", "Tesla", "War", "World",
]

# Dominant categories per simulated-user archetype
_ARCHETYPE_DOMINANT: Dict[str, List[str]] = {
    "news_junkie":    ["Politics", "World", "Elections", "War", "Business"],
    "casual_browser": ["Entertainment", "Movies", "Sports", "Cricket"],
    "deep_reader":    ["Science", "Technology", "AI", "World", "OpenAI"],
    "explorer":       CATEGORIES,   # equal spread
    "sports_fan":     ["Sports", "Cricket", "IPL", "Entertainment"],
}


def _category_weights_for(archetype_name: str) -> Dict[str, float]:
    dominant = _ARCHETYPE_DOMINANT[archetype_name]
    weights = {c: 0.01 for c in CATEGORIES}
    for cat in dominant:
        weights[cat] = random.uniform(0.15, 0.35)
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def generate_user_population(n: int = 100, seed: int = 42) -> List[UserPolicy]:
    random.seed(seed)
    np.random.seed(seed)

    # (curiosity, patience, recency_bias, position_bias, satiation_rate)
    archetypes = [
        {"name": "news_junkie",    "traits": (0.3, 0.8, 0.9, 0.4, 0.2)},
        {"name": "casual_browser", "traits": (0.6, 0.3, 0.4, 0.8, 0.5)},
        {"name": "deep_reader",    "traits": (0.2, 0.9, 0.3, 0.2, 0.1)},
        {"name": "explorer",       "traits": (0.9, 0.5, 0.5, 0.5, 0.7)},
        {"name": "sports_fan",     "traits": (0.1, 0.6, 0.7, 0.6, 0.3)},
    ]

    users = []
    for i in range(n):
        arch = archetypes[i % len(archetypes)]
        c, pa, r, pb, s = arch["traits"]

        def noisy(x): return float(np.clip(x + np.random.normal(0, 0.1), 0.05, 0.95))

        policy = UserPolicy(
            user_id=f"user_{i:03d}_{arch['name']}",
            category_weights=_category_weights_for(arch["name"]),
            curiosity=noisy(c),
            patience=noisy(pa),
            recency_bias=noisy(r),
            position_bias=noisy(pb),
            satiation_rate=noisy(s),
            session_length=random.randint(5, 20),
            active_hours=random.sample(range(6, 23), random.randint(3, 6)),
            mood_volatility=random.uniform(0.2, 0.8),
        )
        users.append(policy)

    return users


# ── reward function for RL ───────────────────────────────────────────────────

def compute_reward(interactions: List[Dict]) -> float:
    """
    Compute reward from one feed interaction.
    Called by your RL environment after UserEngine.interact_with_feed().
    """
    if not interactions:
        return -0.5  # user didn't interact at all = bad ranking
    
    reward = 0.0
    n = len(interactions)
    
    action_values = {
        'share':       +3.0,
        'dwell_long':  +2.0,
        'click':       +1.0,
        'dwell_short': -0.5,
        'skip':        -0.2,
    }
    
    for interaction in interactions:
        action_val = action_values[interaction['action']]
        
        # position discount: reward is worth more if good action happened early
        position_discount = 1.0 / np.log2(interaction['position'] + 2)
        reward += action_val * position_discount
    
    # diversity bonus: entropy over categories interacted with
    cats = [i['category'] for i in interactions]
    cat_counts = {c: cats.count(c) for c in set(cats)}
    probs = np.array(list(cat_counts.values())) / len(cats)
    entropy = -np.sum(probs * np.log(probs + 1e-8))
    max_entropy = np.log(len(CATEGORIES)) if len(CATEGORIES) > 1 else 1.0
    diversity_bonus = 0.4 * (entropy / max_entropy)
    
    # mood trajectory bonus: did mood improve during session?
    if len(interactions) > 1:
        mood_start = interactions[0]['mood_before']
        mood_end = interactions[-1]['mood_before']
        mood_bonus = 0.3 * (mood_end - mood_start)
        reward += mood_bonus
    
    reward += diversity_bonus
    return float(reward)


# ── usage example ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    
    # generate population
    users = generate_user_population(n=100)
    print(f"Generated {len(users)} users")
    print(f"Example user: {users[0].user_id}")
    print(f"  category weights: {users[0].category_weights}")
    print(f"  curiosity={users[0].curiosity:.2f}, patience={users[0].patience:.2f}")
    
    # simulate one interaction (plug in real article vecs from NRMS)
    engine = UserEngine(users[0])
    state  = engine.start_session()
    
    # dummy articles — replace with real MIND articles + NRMS vecs
    dummy_articles = [
        Article(
            id=f'N{i}',
            category=random.choice(CATEGORIES),
            subcategory='general',
            title=f'Article {i}',
            vec=np.random.randn(256).astype(np.float32),
            freshness=random.random()
        )
        for i in range(20)
    ]
    
    interactions, state = engine.interact_with_feed(dummy_articles, state)
    reward = compute_reward(interactions)
    
    print(f"\nSession interactions: {len(interactions)}")
    for ix in interactions:
        print(f"  pos={ix['position']:2d}  {ix['action']:12s}  "
              f"cat={ix['category']:15s}  relevance={ix['relevance']:.2f}")
    print(f"\nReward: {reward:.3f}")
    
    # save policies to disk so they're reproducible
    policies_json = []
    for u in users:
        policies_json.append({
            'user_id': u.user_id,
            'category_weights': u.category_weights,
            'curiosity': u.curiosity,
            'patience': u.patience,
            'recency_bias': u.recency_bias,
            'position_bias': u.position_bias,
            'satiation_rate': u.satiation_rate,
            'session_length': u.session_length,
            'active_hours': u.active_hours,
            'mood_volatility': u.mood_volatility,
        })
    
    with open('user_policies.json', 'w') as f:
        json.dump(policies_json, f, indent=2)
    print("\nSaved 100 user policies to user_policies.json")