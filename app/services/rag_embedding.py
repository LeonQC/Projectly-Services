"""
一条或多条文本
→ Local SentenceTransformer: sentence-transformers/all-MiniLM-L6-v2
→ 批量生成 embedding
→ normalized vector(384)
→ 验证向量维度
输出：
→ list[list[float]]

get_embedding_model()
create_embeddings()
count_tokens()
"""
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import settings

# 加载本地模型
@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    model = SentenceTransformer(settings.embedding_model)

    return model

# 统一输入格式：传入一条文本或者多条文本
def normalize_embedding_inputs(
    inputs: str | list[str],
) -> list[str]:
    if isinstance(inputs, str):
        normalized_inputs = [inputs]
    else:
        normalized_inputs = inputs

    normalized_inputs = [
        text.strip()
        for text in normalized_inputs
        if text and text.strip()
    ]

    return normalized_inputs

# 创建embedding
def create_embeddings(
    inputs: str | list[str],
    *,
    batch_size: int = 32,
) -> list[list[float]]:
    normalized_inputs = normalize_embedding_inputs(inputs)

    if not normalized_inputs:
        return []

    model = get_embedding_model()

    embeddings = model.encode(
        normalized_inputs,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    vectors = embeddings.tolist()

    for vector in vectors:
        if len(vector) != settings.embedding_dimensions:
            raise RuntimeError(
                "Embedding dimension mismatch: "
                f"expected {settings.embedding_dimensions}, "
                f"got {len(vector)}"
            )

    return vectors
