# ==========================================================
# TAG-BASED NEWS RECOMMENDER — JSON VERSION
# Uses google_news_5000.json with real category labels
# 3 fake users, 50 reads each, Top-20 recommendations
# ==========================================================

import json
import random
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# ==========================================================
# CONFIG
# ==========================================================
JSON_PATH     = "google_news_5000.json"
MODEL_NAME    = "BAAI/bge-reranker-base"

NUM_FAKE_USERS = 3
TOP_K          = 20
NUM_READS      = 50          # articles each user reads

MAIN_TAG_RATIO = 0.5         # 80% reads from preferred category
TAG_BOOST      = 0.0         # score bonus for preferred-category candidates

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

random.seed(42)

# ==========================================================
# LOAD DATA
# ==========================================================
print("=" * 70)
print("Starting News Recommendation Generation (JSON mode)")
print("=" * 70)

with open(JSON_PATH, "r", encoding="utf-8") as f:
    raw = json.load(f)

df = pd.DataFrame(raw)
df = df.fillna("")
df["article_id"] = range(len(df))

# Use title + summary as the article text fed to the reranker
df["article_text"] = (
    "Title: " + df["title"].astype(str) +
    " Summary: " + df["summary"].astype(str)
)

print(f"Loaded {len(df)} articles")
print(f"Categories: {sorted(df['category'].unique().tolist())}")
print()

# ==========================================================
# LOAD MODEL
# ==========================================================
print("Loading reranker model... please wait")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model     = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
model.to(DEVICE)
model.eval()
print("Model loaded\n")

# ==========================================================
# INFERENCE FUNCTION
# ==========================================================
@torch.no_grad()
def score_pairs(query, docs, batch_size=8):
    scores = []
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        pairs  = [[query, d] for d in batch]
        inputs = tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        )
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        logits = model(**inputs).logits.view(-1).cpu().tolist()
        scores.extend(logits)
    return scores

# ==========================================================
# BUILD FOCUSED QUERY FROM HISTORY
# Use category label + up to 5 representative titles
# ==========================================================
def build_query(pref_cat, read_ids, df, max_titles=5):
    history_df = df[df["article_id"].isin(read_ids)]
    # prioritise titles from the preferred category
    cat_titles   = history_df[history_df["category"] == pref_cat]["title"].tolist()
    other_titles = history_df[history_df["category"] != pref_cat]["title"].tolist()
    selected = cat_titles[:max_titles]
    if len(selected) < max_titles:
        selected += other_titles[: max_titles - len(selected)]
    titles_str = " | ".join(selected)
    return f"{pref_cat} news. Examples: {titles_str}"

# ==========================================================
# CREATE FAKE USERS
# ==========================================================
print(f"Creating {NUM_FAKE_USERS} fake users ({NUM_READS} reads each)...\n")

all_cats = df["category"].dropna().unique().tolist()
users    = []

for u in range(1, NUM_FAKE_USERS + 1):
    pref_cat   = random.choice(all_cats)
    main_count = int(NUM_READS * MAIN_TAG_RATIO)  # 40 from preferred
    rand_count = NUM_READS - main_count            # 10 from other categories

    cat_pool  = df[df["category"] == pref_cat]["article_id"].tolist()
    main_reads = random.sample(cat_pool, min(main_count, len(cat_pool)))

    other_pool = df[
        (~df["article_id"].isin(main_reads)) &
        (df["category"] != pref_cat)
    ]["article_id"].tolist()
    other_reads = random.sample(other_pool, min(rand_count, len(other_pool)))

    read_ids = main_reads + other_reads
    random.shuffle(read_ids)

    users.append({
        "user_id"      : f"USER_{u:02d}",
        "preferred_cat": pref_cat,
        "read_ids"     : read_ids,
    })
    print(f"  USER_{u:02d} | Preferred Category: {pref_cat} | Total reads: {len(read_ids)}")

# ==========================================================
# PRINT READ ARTICLES FOR EACH USER
# ==========================================================
print("\n" + "=" * 70)
print("READ HISTORY PER USER")
print("=" * 70)

for user in users:
    uid      = user["user_id"]
    pref_cat = user["preferred_cat"]
    read_ids = user["read_ids"]

    print(f"\n[{uid}]  Preferred Category: {pref_cat}  |  Total articles read: {len(read_ids)}")
    print("-" * 70)
    print(f"{'#':<4}  {'Category':<15}  Title")
    print(f"{'─'*4}  {'─'*15}  {'─'*48}")
    for i, rid in enumerate(read_ids, 1):
        row = df[df["article_id"] == rid].iloc[0]
        title_short = row["title"][:65] + ("..." if len(row["title"]) > 65 else "")
        print(f"{i:<4}  {row['category']:<15}  {title_short}")

# ==========================================================
# GENERATE RECOMMENDATIONS
# ==========================================================
print("\n" + "=" * 70)
print("TOP-20 RECOMMENDATIONS PER USER")
print("=" * 70)

results = []

for user in users:
    uid      = user["user_id"]
    pref_cat = user["preferred_cat"]
    read_ids = user["read_ids"]

    print(f"\n[{uid}] Running inference (preferred: {pref_cat})...")

    query = build_query(pref_cat, read_ids, df)
    print(f"[{uid}] Query: {query[:110]}...")

    candidate_df = df[~df["article_id"].isin(read_ids)].copy()
    docs         = candidate_df["article_text"].tolist()

    scores = score_pairs(query, docs)
    print(f"[{uid}] Scored {len(scores)} candidate articles")

    candidate_df = candidate_df.copy()
    candidate_df["logit_score"] = scores
    candidate_df["tag_boost"]   = candidate_df["category"].apply(
        lambda c: TAG_BOOST if c == pref_cat else 0.0
    )
    candidate_df["final_score"] = candidate_df["logit_score"] + candidate_df["tag_boost"]
    candidate_df = candidate_df.sort_values("final_score", ascending=False)

    top20 = candidate_df.head(TOP_K)

    # Print top-20 nicely
    print(f"\n{'─'*70}")
    print(f"  TOP-20 RECOMMENDATIONS FOR {uid}  (preferred: {pref_cat})")
    print(f"{'─'*70}")
    print(f"{'Rank':<5}  {'Category':<15}  {'Score':>7}  Title")
    print(f"{'─'*5}  {'─'*15}  {'─'*7}  {'─'*42}")

    for rank, (_, row) in enumerate(top20.iterrows(), start=1):
        title_short = row["title"][:55] + ("..." if len(row["title"]) > 55 else "")
        print(f"{rank:<5}  {row['category']:<15}  {row['final_score']:>7.3f}  {title_short}")

        results.append(int(row["story_id"]))

    # Category distribution summary
    cat_dist = top20["category"].value_counts().to_dict()
    print(f"\n  Category breakdown in top-20: {cat_dist}")
    print(f"{'─'*70}")

# ==========================================================
# SAVE OUTPUT
# ==========================================================
print("\nSaving results...")
with open("recommendations_output.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("Saved: recommendations_output.json")
print("\n" + "=" * 70)
print("Done!")
print("=" * 70)