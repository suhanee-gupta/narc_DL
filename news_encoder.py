"""
Offline batch script — run once to produce news_vectors.pkl.
This is the ONLY file that reads raw article text or source embeddings.
Everything downstream receives only news_vectors.pkl.

Usage:
    python news_encoder.py \
        --news news.tsv \
        --distilbert distilbert_embeddings.pkl \
        --entity entity_embedding.vec \
        --relation relation_embedding.vec \
        --out news_vectors.pkl
"""

import json
import pickle
import argparse
import numpy as np
import torch
import torch.nn as nn
from config import VEC_DIM, DISTILBERT_DIM, ENCODER_SEED


class NewsEncoder:
    def __init__(
        self,
        news_tsv: str,
        distilbert_pkl: str,
        entity_vec_path: str,
        relation_vec_path: str,
        out_dim: int = VEC_DIM,
        seed: int = ENCODER_SEED,
    ):
        self.news_tsv = news_tsv
        self.out_dim = out_dim

        print("Loading DistilBERT embeddings...")
        with open(distilbert_pkl, "rb") as f:
            self._distilbert: dict = pickle.load(f)

        print("Loading entity embeddings...")
        self._entity_emb, self.entity_dim = self._load_embedding_file(entity_vec_path)

        print("Loading relation embeddings...")
        self._relation_emb, self.relation_dim = self._load_embedding_file(relation_vec_path)

        input_dim = DISTILBERT_DIM + self.entity_dim + self.relation_dim
        print(f"Projection: {input_dim} → {out_dim}  (Xavier uniform, frozen)")

        torch.manual_seed(seed)
        self._proj = nn.Linear(input_dim, out_dim, bias=False)
        nn.init.xavier_uniform_(self._proj.weight)
        self._proj.eval()
        for p in self._proj.parameters():
            p.requires_grad_(False)

    # ── file loaders ────────────────────────────────────────────────────────

    def _load_embedding_file(self, path: str) -> tuple[dict, int]:
        """
        Reads a .vec file:
          line 0:  num_entities  embedding_dim
          lines 1+: entity_id  f1  f2  ...  fD
        Returns ({entity_id: np.array(D,)}, D).
        """
        embeddings: dict[str, np.ndarray] = {}
        with open(path, "r", encoding="utf-8") as f:
            num_str, dim_str = f.readline().strip().split()
            dim = int(dim_str)
            for line in f:
                parts = line.rstrip().split(" ")
                if len(parts) != dim + 1:
                    continue
                embeddings[parts[0]] = np.array(parts[1:], dtype=np.float32)
        return embeddings, dim

    # ── per-article helpers ──────────────────────────────────────────────────

    def _mean_entity_vec(self, json_str: str, embed_dict: dict, dim: int) -> np.ndarray:
        try:
            entities = json.loads(json_str) if json_str.strip() else []
        except (json.JSONDecodeError, AttributeError):
            entities = []

        vecs = [
            embed_dict[e["WikidataId"]]
            for e in entities
            if isinstance(e, dict) and e.get("WikidataId") in embed_dict
        ]
        return np.mean(vecs, axis=0) if vecs else np.zeros(dim, dtype=np.float32)

    # ── main encoding pass ───────────────────────────────────────────────────

    def encode_all(self) -> dict[str, np.ndarray]:
        results: dict[str, np.ndarray] = {}

        with open(self.news_tsv, "r", encoding="utf-8") as f:
            rows = [line.rstrip("\n").split("\t") for line in f]

        total = len(rows)
        print(f"Encoding {total} articles...")

        for i, row in enumerate(rows):
            if len(row) < 8:
                continue

            news_id = row[0]
            title_entities_str = row[6]
            abstract_entities_str = row[7]

            if news_id not in self._distilbert:
                continue

            distilbert_vec = np.asarray(self._distilbert[news_id], dtype=np.float32)
            if distilbert_vec.shape != (DISTILBERT_DIM,):
                continue

            # entity vec: mean over title + abstract entities
            t_vec = self._mean_entity_vec(title_entities_str, self._entity_emb, self.entity_dim)
            a_vec = self._mean_entity_vec(abstract_entities_str, self._entity_emb, self.entity_dim)
            non_zero = [v for v in (t_vec, a_vec) if np.any(v != 0)]
            entity_vec = np.mean(non_zero, axis=0) if non_zero else np.zeros(self.entity_dim, dtype=np.float32)

            # relation vec: zero — MIND has no per-article relation IDs
            relation_vec = np.zeros(self.relation_dim, dtype=np.float32)

            combined = np.concatenate([distilbert_vec, entity_vec, relation_vec])

            with torch.no_grad():
                t = torch.from_numpy(combined).float().unsqueeze(0)
                projected = self._proj(t).squeeze(0).numpy()

            results[news_id] = projected

            if (i + 1) % 5000 == 0:
                print(f"  {i + 1}/{total}")

        print(f"Encoded {len(results)} articles.")
        return results

    def save(self, out_path: str = "news_vectors.pkl") -> None:
        vectors = self.encode_all()
        with open(out_path, "wb") as f:
            pickle.dump(vectors, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"Saved → {out_path}")


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Produce news_vectors.pkl from MIND files.")
    parser.add_argument("--news",       required=True, help="Path to news.tsv")
    parser.add_argument("--distilbert", required=True, help="Path to distilbert_embeddings.pkl")
    parser.add_argument("--entity",     required=True, help="Path to entity_embedding.vec")
    parser.add_argument("--relation",   required=True, help="Path to relation_embedding.vec")
    parser.add_argument("--out",        default="news_vectors.pkl", help="Output path")
    args = parser.parse_args()

    encoder = NewsEncoder(
        news_tsv=args.news,
        distilbert_pkl=args.distilbert,
        entity_vec_path=args.entity,
        relation_vec_path=args.relation,
    )
    encoder.save(args.out)
