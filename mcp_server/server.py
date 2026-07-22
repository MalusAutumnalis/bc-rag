# mcp_server/server.py
import chromadb
import requests
from embedder import embed_query
from mcp.server.fastmcp import FastMCP

LM_STUDIO_URL = "http://127.0.0.1:1234/v1/embeddings"
EMBED_MODEL = "bge-m3"

mcp = FastMCP("black-crusade-rules")
client = chromadb.PersistentClient(path="chroma_db")
coll = client.get_collection("black_crusade")

def embed_query(text: str) -> list[float]:
    r = requests.post(LM_STUDIO_URL, json={"model": EMBED_MODEL, "input": [text]})
    return r.json()["data"][0]["embedding"]

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