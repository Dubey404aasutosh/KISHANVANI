import json
import pickle
import os
import torch
from pathlib import Path
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

PROCESSED_DATA_PATH = Path("data/processed/kcc_national.json")
INDEX_DIR = Path("data/index")

def tokenize(text):
    # Simple tokenizer covering all Indic scripts + English: split by space,
    # lower (mainly affects English/Latin tokens), strip basic punctuation.
    # Indic scripts (Devanagari, Gujarati, Gurmukhi, Bengali, Tamil, Telugu,
    # Kannada, etc.) have no case, so lower() is a no-op for them and this
    # tokenizer works uniformly across all target languages.
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text.split()

def main():
    print("Loading processed data...")
    if not PROCESSED_DATA_PATH.exists():
        print(f"Error: {PROCESSED_DATA_PATH} not found. Run ingest/fetch_kcc.py first.")
        return

    with open(PROCESSED_DATA_PATH, 'r', encoding='utf-8') as f:
        records = json.load(f)

    if not records:
        print("No records found to index.")
        return

    # Prepare corpus for indexing
    # We index the concatenation of query and answer to capture intent and content.
    corpus_texts = []
    for r in records:
        text = f"{r.get('query', '')} {r.get('answer', '')}"
        corpus_texts.append(text)

    # 1. Build BM25 Index
    print("Building BM25 Index...")
    tokenized_corpus = [tokenize(doc) for doc in corpus_texts]
    bm25 = BM25Okapi(tokenized_corpus)

    # 2. Build Dense Embeddings
    print("Building Dense Embeddings (multilingual-e5-base)...")
    # For E5 models, prefixing 'passage: ' to corpus is recommended.
    e5_corpus = [f"passage: {text}" for text in corpus_texts]
    
    # We use a smaller multilingual model to ensure it runs quickly on prototypes.
    model = SentenceTransformer('intfloat/multilingual-e5-base')
    embeddings = model.encode(e5_corpus, convert_to_tensor=True, show_progress_bar=True)

    # 3. Save Index
    print("Saving Index...")
    os.makedirs(INDEX_DIR, exist_ok=True)
    
    with open(INDEX_DIR / "corpus_records.json", 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=4)
        
    with open(INDEX_DIR / "bm25_index.pkl", 'wb') as f:
        pickle.dump(bm25, f)
        
    torch.save(embeddings, INDEX_DIR / "dense_embeddings.pt")

    print(f"Successfully indexed {len(records)} records in {INDEX_DIR}/")

if __name__ == "__main__":
    main()
