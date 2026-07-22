# ingest/build_index.py
import chromadb
from pathlib import Path
from chunker import chunk_file
from config import load_sources
from embedder import embed_passages
import hashlib

def make_chunk_id(path: Path, root: Path, index: int) -> str:
    rel = path.relative_to(root).as_posix()  # "рукопашное оружие/базовое.md"
    # хешируем, чтобы не тащить кириллицу/пробелы в id и не упереться в лимиты длины
    h = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
    return f"{h}-{index}"

def build():
    client = chromadb.PersistentClient(path="chroma_db")
    coll = client.get_or_create_collection("black_crusade")

    cfg = load_sources()
    sources = [
        (cfg["core_rules_path"], "core"),
        (cfg["homebrew_path"], "homebrew"),
    ]

    ids, docs, metas = [], [], []
    for folder, stype in sources:
        root = Path(folder)
        for path in root.rglob("*.md"):
            for i, ch in enumerate(chunk_file(path, stype)):
                if not ch.text.strip():
                    continue
                ids.append(make_chunk_id(path, root, i))
                docs.append(ch.text)
                metas.append({
                    "heading": ch.heading_path,
                    "file": ch.source_file,
                    "source_type": ch.source_type,
                })

    if not docs:
        print("Нет документов для индексации")
        return

    B = 32
    for i in range(0, len(docs), B):
        batch_docs = docs[i:i+B]
        batch_ids = ids[i:i+B]
        batch_metas = metas[i:i+B]

        embs = embed_passages(batch_docs)
        coll.add(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_metas,
            embeddings=embs,
        )
        print(f"Проиндексировано {i + len(batch_docs)}/{len(docs)} чанков")
        
    print(f"Готово. Всего: {len(docs)} чанков")


if __name__ == "__main__":
    build()