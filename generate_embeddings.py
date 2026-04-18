"""
Offline script: generate title_embeddings.pkl using BAAI/bge-small-en-v1.5.
Produces a (N, 768) numpy array aligned to google_news_5000.json order.

Usage:  python generate_embeddings.py
"""
import json, pickle, torch
import numpy as np
from transformers import AutoTokenizer, AutoModel

MODEL_NAME = "BAAI/bge-small-en-v1.5"
JSON_PATH  = "google_news_5000.json"
OUT_PATH   = "title_embeddings.pkl"

print(f"Loading model: {MODEL_NAME}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model     = AutoModel.from_pretrained(MODEL_NAME)
model.eval()

device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)
print(f"Model on {device}")

# Load articles
with open(JSON_PATH, "r", encoding="utf-8") as f:
    articles = json.load(f)
print(f"Articles loaded: {len(articles)}")

titles = [a.get("title", "") for a in articles]

# Encode in batches
BATCH = 64
all_embeddings = []
for i in range(0, len(titles), BATCH):
    batch = titles[i:i+BATCH]
    inputs = tokenizer(batch, padding=True, truncation=True,
                       max_length=128, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    # CLS pooling
    emb = outputs.last_hidden_state[:, 0, :].cpu().numpy()
    all_embeddings.append(emb)
    if (i // BATCH) % 10 == 0:
        print(f"  encoded {min(i+BATCH, len(titles))}/{len(titles)}")

embeddings = np.vstack(all_embeddings).astype(np.float32)
# L2 normalize
norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
embeddings = embeddings / (norms + 1e-8)

print(f"Final shape: {embeddings.shape}")  # (4860, 384) for bge-small

# bge-small is 384-dim, but pipeline expects 768. Pad with zeros.
if embeddings.shape[1] < 768:
    pad_width = 768 - embeddings.shape[1]
    embeddings = np.pad(embeddings, ((0, 0), (0, pad_width)), constant_values=0.0)
    print(f"Padded to: {embeddings.shape}")

with open(OUT_PATH, "wb") as f:
    pickle.dump(embeddings, f)
print(f"Saved → {OUT_PATH}")
