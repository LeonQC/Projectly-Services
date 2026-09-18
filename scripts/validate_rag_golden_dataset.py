import argparse
import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.project import RagChunk

DEFAULT_DATASET_PATH = Path(
    "evals/datasets/projectly_rag_golden.jsonl"
)


class EvaluationScope(BaseModel):
    workspace_id: int | None = None
    project_id: int | None = None
    card_id: int | None = None

    @model_validator(mode="after")
    def validate_single_scope(self) -> "EvaluationScope":
        values = [
            self.workspace_id,
            self.project_id,
            self.card_id,
        ]

        if sum(value is not None for value in values) != 1:
            raise ValueError(
                "scope must contain exactly one of "
                "workspace_id, project_id, or card_id"
            )

        return self


class ReferenceSource(BaseModel):
    source_type: str = Field(min_length=1)
    source_id: int


class GoldenSample(BaseModel):
    id: str = Field(min_length=1)
    scope: EvaluationScope
    user_input: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    reference_sources: list[ReferenceSource]
    tags: list[str] = Field(default_factory=list)


def load_and_validate_dataset(
    dataset_path: Path,
) -> list[GoldenSample]:
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}"
        )

    samples: list[GoldenSample] = []
    sample_ids: set[str] = set()
    errors: list[str] = []

    with dataset_path.open(encoding="utf-8") as dataset_file:
        for line_number, raw_line in enumerate(
            dataset_file,
            start=1,
        ):
            line = raw_line.strip()

            if not line:
                continue

            try:
                raw_sample = json.loads(line)
                sample = GoldenSample.model_validate(raw_sample)
            except json.JSONDecodeError as exc:
                errors.append(
                    f"Line {line_number}: invalid JSON: {exc}"
                )
                continue
            except ValidationError as exc:
                errors.append(
                    f"Line {line_number}: validation failed:\n{exc}"
                )
                continue

            if sample.id in sample_ids:
                errors.append(
                    f"Line {line_number}: duplicate id: {sample.id}"
                )
                continue

            sample_ids.add(sample.id)
            samples.append(sample)

    if errors:
        raise ValueError("\n\n".join(errors))

    if not samples:
        raise ValueError("Dataset does not contain any samples")

    return samples

def validate_reference_sources(
    samples: list[GoldenSample],
) -> None:
    errors: list[str] = []

    with SessionLocal() as db:
        for sample in samples:
            for reference_source in sample.reference_sources:
                statement = select(RagChunk.id).where(
                    RagChunk.source_type
                    == reference_source.source_type,
                    RagChunk.source_id
                    == reference_source.source_id,
                )

                if sample.scope.card_id is not None:
                    statement = statement.where(
                        RagChunk.card_id == sample.scope.card_id
                    )
                elif sample.scope.project_id is not None:
                    statement = statement.where(
                        RagChunk.project_id
                        == sample.scope.project_id
                    )
                elif sample.scope.workspace_id is not None:
                    statement = statement.where(
                        RagChunk.workspace_id
                        == sample.scope.workspace_id
                    )

                chunk_id = db.scalar(statement.limit(1))

                if chunk_id is None:
                    errors.append(
                        (
                            f"Sample {sample.id}: source "
                            f"{reference_source.source_type}:"
                            f"{reference_source.source_id} "
                            "does not exist in the declared scope"
                        )
                    )

    if errors:
        raise ValueError("\n".join(errors))

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the Projectly RAG golden dataset."
    )
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )
    args = parser.parse_args()

    samples = load_and_validate_dataset(args.dataset)
    validate_reference_sources(samples)

    tag_counts: dict[str, int] = {}
    for sample in samples:
        for tag in sample.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    print(f"Dataset: {args.dataset}")
    print(f"Valid samples: {len(samples)}")
    print(f"Unique IDs: {len({sample.id for sample in samples})}")
    print(f"Tags: {tag_counts}")
    print("Reference sources: valid")


if __name__ == "__main__":
    main()