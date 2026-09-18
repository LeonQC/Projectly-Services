# Projectly RAG Evaluation

This directory contains the manually reviewed golden dataset and generated
evaluation results for the Projectly RAG pipeline.

## Structure

- `datasets/projectly_rag_golden.jsonl`: manually reviewed evaluation samples
- `experiments/`: generated evaluation reports

## Golden Sample Fields

- `id`: stable unique identifier for the test case
- `scope`: exactly one of `workspace_id`, `project_id`, or `card_id`
- `user_input`: question sent to the RAG pipeline
- `reference`: manually reviewed expected answer
- `reference_sources`: expected source records identified by `source_type` and
  `source_id`
- `tags`: categories used to group evaluation results

## Dataset Rules

1. Each line must contain one valid JSON object.
2. Each sample must declare exactly one retrieval scope.
3. Reference answers must only use information available in the declared scope.
4. Reference sources must exist in `rag_chunks`.
5. Use `source_type` and `source_id` instead of `chunk_id`, because chunk IDs may
   change after reindexing.
6. Include answerable, multi-source, paraphrased, and unanswerable questions.
7. Golden answers and expected sources must be manually reviewed.

## Validation

Run:

```bash
.venv/bin/python -m scripts.validate_rag_golden_dataset
```
