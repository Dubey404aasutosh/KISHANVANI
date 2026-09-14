import json
import pickle
import torch
from pathlib import Path
from sentence_transformers import SentenceTransformer, util
import re

INDEX_DIR = Path("data/index")

class HybridRetriever:
    def __init__(self):
        print("Loading Hybrid Index...")
        with open(INDEX_DIR / "corpus_records.json", 'r', encoding='utf-8') as f:
            self.records = json.load(f)
            
        with open(INDEX_DIR / "bm25_index.pkl", 'rb') as f:
            self.bm25 = pickle.load(f)

        self.model = SentenceTransformer('intfloat/multilingual-e5-base')
        # Keep every tensor on the same device as the model (GPU if available,
        # else CPU). Embeddings are saved/loaded on CPU by build_index.py, so
        # move them here rather than assuming a device match.
        self.device = self.model.device
        self.embeddings = torch.load(INDEX_DIR / "dense_embeddings.pt", weights_only=True).to(self.device)
        
    def _tokenize(self, text):
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        return text.split()

    def retrieve(self, query, k=3, alpha=0.5, crop=None, state=None):
        """
        Hybrid retrieval combining BM25 and Dense scores, over the full
        national, multi-crop corpus.
        alpha: weight for dense score (0.0 = only BM25, 1.0 = only Dense)
        We use min-max scaling for combination since RRF can be overkill for small datasets.
        crop/state: optional filters (e.g. "cotton", "gujarat") to narrow the
            search space when the farmer's crop/location is known (e.g. from
            an IVR menu or caller registration) - this both speeds up search
            and avoids cross-crop/state advice bleeding into the answer.
        """
        if not self.records:
            return []

        # Optional pre-filter by crop/state before scoring, so a farmer
        # asking about cotton in Gujarat doesn't get a rice/Punjab passage
        # just because it scores textually similar.
        candidate_indices = list(range(len(self.records)))
        if crop:
            crop = crop.strip().lower()
            candidate_indices = [i for i in candidate_indices
                                  if self.records[i].get('crop', '').lower() == crop]
        if state:
            state = state.strip().lower()
            candidate_indices = [i for i in candidate_indices
                                  if self.records[i].get('state', '').lower() == state]
        if not candidate_indices:
            # Filters too narrow / no match -> fall back to searching everything.
            candidate_indices = list(range(len(self.records)))

        # 1. BM25 Scores
        tokenized_query = self._tokenize(query)
        full_bm25_scores = torch.tensor(self.bm25.get_scores(tokenized_query), dtype=torch.float32, device=self.device)
        bm25_scores = full_bm25_scores[candidate_indices]

        # 2. Dense Scores
        e5_query = f"query: {query}"
        query_embedding = self.model.encode(e5_query, convert_to_tensor=True)
        full_dense_scores = util.cos_sim(query_embedding, self.embeddings)[0]
        dense_scores = full_dense_scores[candidate_indices]

        # 3. Normalize Scores (Min-Max Scaling)
        def min_max_scale(scores):
            min_val, max_val = scores.min(), scores.max()
            if max_val - min_val < 1e-6:
                return torch.zeros_like(scores)
            return (scores - min_val) / (max_val - min_val)

        norm_bm25 = min_max_scale(bm25_scores)
        norm_dense = min_max_scale(dense_scores)

        # 4. Combine
        hybrid_scores = (alpha * norm_dense) + ((1 - alpha) * norm_bm25)

        # 5. Get top k (indices are relative to candidate_indices)
        top_k_local = torch.topk(hybrid_scores, min(k, len(candidate_indices))).indices.tolist()

        results = []
        for local_idx in top_k_local:
            global_idx = candidate_indices[local_idx]
            res = self.records[global_idx].copy()
            res['score'] = float(hybrid_scores[local_idx])
            results.append(res)

        return results

if __name__ == "__main__":
    retriever = HybridRetriever()
    
    test_queries = [
        "મારો કપાસમાં ગુલાબી ઈયળ છે.",          # Pink bollworm in Gujarati
        "कपास में सफेद मक्खी का इलाज",          # Whitefly in Hindi
        "Cotton leaves turning yellow jassids"  # Mixed/English intent
    ]
    
    for q in test_queries:
        print(f"\n--- Query: {q} ---")
        results = retriever.retrieve(q, k=2)
        for i, res in enumerate(results, 1):
            print(f"{i}. [Score: {res['score']:.3f}] {res['answer'][:100]}...")
