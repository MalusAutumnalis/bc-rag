from sentence_transformers import SentenceTransformer

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(
            "intfloat/multilingual-e5-base",
            device="cpu",
        )
    return _model

def embed_passages(texts: list[str]) -> list[list[float]]:
    prefixed = [f"passage: {t}" for t in texts]
    return get_model().encode(prefixed, normalize_embeddings=True).tolist()

def embed_query(text: str) -> list[float]:
    return get_model().encode([f"query: {text}"], normalize_embeddings=True)[0].tolist()