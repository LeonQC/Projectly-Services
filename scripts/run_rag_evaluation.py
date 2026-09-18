import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from openai import AsyncOpenAI
from ragas.embeddings import HuggingFaceEmbeddings
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerCorrectness,
    AnswerRelevancy,
    ContextPrecisionWithReference,
    ContextRecall,
    Faithfulness,
)

from app.core.config import settings

from app.db.session import SessionLocal
from app.models.project import RagChunk
from app.schemas.rag import RagAskRequest
from app.services.rag_answering import answer_rag_question
from scripts.validate_rag_golden_dataset import (
    DEFAULT_DATASET_PATH,
    GoldenSample,
    load_and_validate_dataset,
    validate_reference_sources,
)


DEFAULT_OUTPUT_DIRECTORY = Path("evals/experiments")


def source_key(
    source_type: str,
    source_id: int,
) -> str:
    return f"{source_type}:{source_id}"


def calculate_retrieval_metrics(
    sample: GoldenSample,
    retrieved_sources: list[dict],
) -> dict[str, float | None]:
    reference_keys = {
        source_key(source.source_type, source.source_id)
        for source in sample.reference_sources
    }

    retrieved_keys = [
        source_key(
            source["source_type"],
            source["source_id"],
        )
        for source in retrieved_sources
    ]
    unique_retrieved_keys = set(retrieved_keys)

    if not reference_keys:
        return {
            "source_precision": None,
            "source_recall": None,
            "source_mrr": None,
        }

    matching_keys = reference_keys & unique_retrieved_keys

    precision = (
        len(matching_keys) / len(unique_retrieved_keys)
        if unique_retrieved_keys
        else 0.0
    )
    recall = len(matching_keys) / len(reference_keys)

    reciprocal_rank = 0.0
    for rank, retrieved_key in enumerate(
        retrieved_keys,
        start=1,
    ):
        if retrieved_key in reference_keys:
            reciprocal_rank = 1.0 / rank
            break

    return {
        "source_precision": precision,
        "source_recall": recall,
        "source_mrr": reciprocal_rank,
    }


def load_retrieved_contexts(
    db,
    chunk_ids: list[int],
) -> list[str]:
    if not chunk_ids:
        return []

    chunks = list(
        db.scalars(
            select(RagChunk).where(RagChunk.id.in_(chunk_ids))
        ).all()
    )
    chunks_by_id = {
        chunk.id: chunk
        for chunk in chunks
    }

    return [
        chunks_by_id[chunk_id].content
        for chunk_id in chunk_ids
        if chunk_id in chunks_by_id
    ]


def evaluate_sample(
    db,
    sample: GoldenSample,
    user_id: int,
    top_k: int,
) -> dict:
    scope = sample.scope.model_dump(exclude_none=True)

    request = RagAskRequest(
        **scope,
        query=sample.user_input,
        top_k=top_k,
    )
    response = answer_rag_question(
        db,
        user_id,
        request,
    )

    retrieved_sources = [
        source.model_dump()
        for source in response.sources
    ]
    chunk_ids = [
        source.chunk_id
        for source in response.sources
    ]
    retrieved_contexts = load_retrieved_contexts(
        db,
        chunk_ids,
    )

    retrieval_metrics = calculate_retrieval_metrics(
        sample,
        retrieved_sources,
    )

    return {
        "id": sample.id,
        "scope": scope,
        "tags": sample.tags,
        "user_input": sample.user_input,
        "reference": sample.reference,
        "reference_sources": [
            source.model_dump()
            for source in sample.reference_sources
        ],
        "response": response.answer,
        "retrieved_contexts": retrieved_contexts,
        "retrieved_sources": retrieved_sources,
        "retrieval_metrics": retrieval_metrics,
        "is_unanswerable": "unanswerable" in sample.tags,
        "abstention_correct": (
            "i don't know based on the available projectly data"
            in response.answer.lower()
            if "unanswerable" in sample.tags
            else None
        ),
    }


def build_output_path(output_directory: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return output_directory / f"projectly_rag_eval_{timestamp}.json"


def build_ragas_metrics() -> dict:
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is required for RAGAS evaluation"
        )

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=120.0,
        max_retries=3,
    )
    evaluator_llm = llm_factory(
        settings.chat_model,
        client=client,
    )
    evaluator_embeddings = HuggingFaceEmbeddings(
        model=settings.embedding_model,
        normalize_embeddings=True,
    )

    return {
        "faithfulness": Faithfulness(
            llm=evaluator_llm,
        ),
        "answer_relevancy": AnswerRelevancy(
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
            strictness=1,
        ),
        "context_precision": ContextPrecisionWithReference(
            llm=evaluator_llm,
        ),
        "context_recall": ContextRecall(
            llm=evaluator_llm,
        ),
        "answer_correctness": AnswerCorrectness(
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
        ),
    }


async def calculate_ragas_metrics(
    result: dict,
    metrics: dict,
) -> dict[str, float | None]:
    user_input = result["user_input"]
    response = result["response"]
    reference = result["reference"]
    retrieved_contexts = result["retrieved_contexts"]

    if result["is_unanswerable"]:
        answer_correctness = await metrics[
            "answer_correctness"
        ].ascore(
            user_input=user_input,
            response=response,
            reference=reference,
        )

        return {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_precision": None,
            "context_recall": None,
            "answer_correctness": float(
                answer_correctness.value
            ),
        }

    scores = {
        "faithfulness": await metrics[
            "faithfulness"
        ].ascore(
            user_input=user_input,
            response=response,
            retrieved_contexts=retrieved_contexts,
        ),
        "answer_relevancy": await metrics[
            "answer_relevancy"
        ].ascore(
            user_input=user_input,
            response=response,
        ),
        "context_precision": await metrics[
            "context_precision"
        ].ascore(
            user_input=user_input,
            reference=reference,
            retrieved_contexts=retrieved_contexts,
        ),
        "context_recall": await metrics[
            "context_recall"
        ].ascore(
            user_input=user_input,
            reference=reference,
            retrieved_contexts=retrieved_contexts,
        ),
        "answer_correctness": await metrics[
            "answer_correctness"
        ].ascore(
            user_input=user_input,
            response=response,
            reference=reference,
        ),
    }

    return {
        name: float(score.value)
        for name, score in scores.items()
    }


async def add_ragas_metrics(
    results: list[dict],
) -> None:
    metrics = build_ragas_metrics()

    for index, result in enumerate(results, start=1):
        print(
            f"[{index}/{len(results)}] "
            f"Running RAGAS for {result['id']}"
        )
        result["ragas_metrics"] = (
            await calculate_ragas_metrics(
                result,
                metrics,
            )
        )


def average_metric(
    values: list[float | None],
) -> float | None:
    numeric_values = [
        value
        for value in values
        if value is not None
    ]

    if not numeric_values:
        return None

    return sum(numeric_values) / len(numeric_values)


def build_evaluation_summary(
    results: list[dict],
) -> dict:
    retrieval_metric_names = [
        "source_precision",
        "source_recall",
        "source_mrr",
    ]
    ragas_metric_names = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_correctness",
    ]

    retrieval_summary = {
        metric_name: average_metric(
            [
                result["retrieval_metrics"].get(metric_name)
                for result in results
            ]
        )
        for metric_name in retrieval_metric_names
    }

    ragas_summary = {
        metric_name: average_metric(
            [
                result["ragas_metrics"].get(metric_name)
                for result in results
            ]
        )
        for metric_name in ragas_metric_names
    }

    unanswerable_results = [
        result
        for result in results
        if result["is_unanswerable"]
    ]

    abstention_accuracy = average_metric(
        [
            1.0 if result["abstention_correct"] else 0.0
            for result in unanswerable_results
        ]
    )

    return {
        "sample_count": len(results),
        "answerable_sample_count": sum(
            not result["is_unanswerable"]
            for result in results
        ),
        "unanswerable_sample_count": len(
            unanswerable_results
        ),
        "retrieval_metrics": retrieval_summary,
        "ragas_metrics": ragas_summary,
        "abstention_accuracy": abstention_accuracy,
    }



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Projectly RAG evaluation dataset."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
    )
    parser.add_argument(
        "--user-id",
        type=int,
        required=True,
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--limit",
        type=int,
    )
    args = parser.parse_args()

    samples = load_and_validate_dataset(args.dataset)
    validate_reference_sources(samples)

    if args.limit is not None:
        samples = samples[:args.limit]

    results: list[dict] = []

    with SessionLocal() as db:
        for index, sample in enumerate(samples, start=1):
            print(
                f"[{index}/{len(samples)}] "
                f"Evaluating {sample.id}"
            )
            result = evaluate_sample(
                db,
                sample,
                args.user_id,
                args.top_k,
            )
            results.append(result)

    asyncio.run(add_ragas_metrics(results))

    output_path = build_output_path(args.output_directory)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "dataset": str(args.dataset),
        "top_k": args.top_k,
        "sample_count": len(results),
        "summary": build_evaluation_summary(results),
        "results": results,
    }

    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Evaluation report: {output_path}")


if __name__ == "__main__":
    main()