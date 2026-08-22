#!/usr/bin/env python3
"""Build RAG index from kb/*.md into chromadb (bge-small-zh embeddings)."""
import os, re, sys, glob
import chromadb
from fastembed import TextEmbedding

os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')

CHUNK_SIZE = 600
OVERLAP = 100

def split_markdown(text):
    """Split md into (title, section, chunk) pieces."""
    lines = text.split('\n')
    doc_title = ''
    sections = []
    cur_sec = []
    cur_sec_title = ''
    for ln in lines:
        if ln.startswith('# '):
            if cur_sec:
                sections.append((cur_sec_title, '\n'.join(cur_sec)))
            doc_title = ln[2:].strip()
            cur_sec = []
            cur_sec_title = ''
        elif ln.startswith('## '):
            if cur_sec:
                sections.append((cur_sec_title, '\n'.join(cur_sec)))
            cur_sec_title = ln[3:].strip()
            cur_sec = []
        else:
            cur_sec.append(ln)
    if cur_sec:
        sections.append((cur_sec_title, '\n'.join(cur_sec)))
    return doc_title, sections

def chunk_section(sec_title, body, doc_title):
    """Split a section body into overlapping chunks."""
    body = body.strip()
    if not body:
        return []
    if len(body) <= CHUNK_SIZE:
        return [(doc_title, sec_title, body)]
    chunks = []
    start = 0
    while start < len(body):
        end = min(start + CHUNK_SIZE, len(body))
        # try to break at newline boundary
        if end < len(body):
            nl = body.rfind('\n', start + CHUNK_SIZE // 2, end)
            if nl != -1:
                end = nl
        chunks.append((doc_title, sec_title, body[start:end].strip()))
        start = end - OVERLAP if end < len(body) else end
    return chunks

def main():
    docs = []
    metas = []
    for fn in sorted(glob.glob('kb/*.md')):
        if fn.endswith('15-广财校历与加分途径.md'):
            continue  # placeholder, skip
        text = open(fn).read()
        doc_title, sections = split_markdown(text)
        for sec_title, body in sections:
            for dt, st, chunk in chunk_section(sec_title, body, doc_title):
                if len(chunk) < 15:
                    continue
                docs.append(chunk)
                metas.append({'source': os.path.basename(fn), 'doc': dt, 'section': st})
    print(f'chunks: {len(docs)}')

    model = TextEmbedding(model_name='BAAI/bge-small-zh-v1.5')
    embeds = list(model.embed(docs, batch_size=32))
    print('embeddings done')

    client = chromadb.PersistentClient(path='rag/index')
    try:
        client.delete_collection('gdufe_guide')
    except Exception:
        pass
    col = client.create_collection('gdufe_guide', metadata={'hnsw:space': 'cosine'})
    col.add(
        ids=[f'c{i}' for i in range(len(docs))],
        documents=docs,
        embeddings=[e.tolist() for e in embeds],
        metadatas=metas,
    )
    print(f'indexed {col.count()} chunks into rag/index')

if __name__ == '__main__':
    main()
