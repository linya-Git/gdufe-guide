#!/usr/bin/env python3
"""RAG search CLI for GDUFE freshman guide.

Usage:
  python3 rag/search.py "宿舍条件怎么样" [--topk 5]
"""
import argparse, os, sys
import chromadb
from fastembed import TextEmbedding

os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')

def search(query, topk=5, with_scores=True):
    client = chromadb.PersistentClient(path='rag/index')
    col = client.get_collection('gdufe_guide')
    model = TextEmbedding(model_name='BAAI/bge-small-zh-v1.5')
    emb = list(model.embed([query]))[0]
    res = col.query(query_embeddings=[emb.tolist()], n_results=topk,
                    include=['documents', 'metadatas', 'distances'])
    out = []
    for doc, meta, dist in zip(res['documents'][0], res['metadatas'][0], res['distances'][0]):
        out.append({
            'text': doc,
            'source': meta['source'],
            'section': meta['section'],
            'score': round(1 - dist, 4),
        })
    return out

def print_results(results):
    for i, r in enumerate(results, 1):
        print(f'--- [{i}] {r["source"]} / {r["section"]} (score={r["score"]}) ---')
        print(r['text'][:800])
        print()

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('query')
    ap.add_argument('--topk', type=int, default=5)
    args = ap.parse_args()
    print_results(search(args.query, args.topk))
