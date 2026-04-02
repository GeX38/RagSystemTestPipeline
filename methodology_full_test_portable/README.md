# Full Methodology Test Pipeline

Russian version: [README.ru.md](./README.ru.md)

This is a standalone file set for reproducing the full canonical evaluation methodology.

Included in the package:

- methodology criteria;
- prompt construction logic for the judge model;
- separate evaluation of blocking criteria and domain criteria;
- deterministic calculation of the final `OKL-score` and class;
- an example input case.

Not included in the package:

- the RAG pipeline;
- retrieval;
- embeddings;
- a database;
- a UI or admin panel;
- a concrete LLM provider implementation.

## What this package does

The package reproduces the full test:

1. accepts `case` and `trajectory`;
2. evaluates separately:
   - blocking criteria;
   - each methodology domain;
3. assembles a composite verdict;
4. calculates:
   - `okl_score`
   - `judge_class`
   - `blocking_failed`
   - domain scores and criteria.

## What you need to provide

The package intentionally **does not include a model implementation**.

You only need to connect your own `judge_client` that implements:

```python
async def complete(*, prompt: str, temperature: float, max_tokens: int) -> str
```

This means the package is not tied to any specific LLM provider.

## Input JSON structure

```json
{
  "case": {
    "title": "Case title",
    "source_reference": "Case source",
    "gold_answer_text": "Expert reference answer",
    "clinical_risk_level": "high",
    "critical_points": ["..."],
    "critical_red_flags": ["..."],
    "interface_warning_present": true
  },
  "trajectory": [
    {
      "stage_index": 1,
      "user_input": "First staged-disclosure step",
      "assistant_answer": "System answer"
    },
    {
      "stage_index": 2,
      "user_input": "Second staged-disclosure step",
      "assistant_answer": "System answer"
    }
  ]
}
```

Important:

- `trajectory` must contain at least 2 stages;
- each stage must contain both `user_input` and `assistant_answer`;
- the full test cannot run without `gold_answer_text`.

## Python API usage

```python
from methodology_full_test_portable.methodology_pipeline import run_full_methodology_test

result = await run_full_methodology_test(
    case_payload=case_payload,
    trajectory=trajectory,
    judge_client=my_judge_client,
    judge_temperature=0.0,
)
```

## Return value

The output is a JSON object with the following structure:

- `method_key`
- `method_version`
- `judge_temperature`
- `case_payload`
- `trajectory`
- `verdict`
- `summary`

Where:

- `verdict` is the raw judge evaluation result;
- `summary` is the deterministic final calculation.
