# mcp_server/server.py
import chromadb
from mcp.server.fastmcp import FastMCP

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from embedder import embed_query

mcp = FastMCP("black-crusade-rules")
client = chromadb.PersistentClient(path="chroma_db")
coll = client.get_collection("black_crusade")

@mcp.tool()
def search_rules(query: str, source: str = "any", k: int = 5) -> str:
    """
    Ищет релевантные правила в Black Crusade (core) и в хоумрул-вики (homebrew).
    source: "core", "homebrew" или "any".
    """
    where = None if source == "any" else {"source_type": source}
    res = coll.query(
        query_embeddings=[embed_query(query)],  
        n_results=k,
        where=where,
    )
    out = []
    for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
        out.append(f"### {meta['heading']} ({meta['source_type']}, {meta['file']})\n{doc}")
    return "\n\n---\n\n".join(out) if out else "Ничего не найдено."

if __name__ == "__main__":
    mcp.run(transport="stdio")