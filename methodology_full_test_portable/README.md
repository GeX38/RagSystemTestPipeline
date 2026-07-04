# methodology_full_test_portable

Languages: [EN](./README.md) | [RU](./README.ru.md)

Repository overview: [../README.md](../README.md)

This directory contains the portable full-methodology module for evaluating a
medical AI assistant. It can be used inside this repository or copied into
another project when you need to run the same evaluation next to your own
system.

## Module purpose

The module accepts a clinical case and a multi-step dialogue trajectory, calls
an external judge model, coerces the model's JSON responses into the expected
schema, and deterministically calculates the final score.

This document describes the module's technical contract. The repository-level
README describes the methodology, scope, and file layout at a higher level.

## Files

- `methodology_pipeline.py`: public `run_full_methodology_test(...)` function
  and minimal CLI skeleton.
- `client_protocol.py`: `JudgeModelProtocol`.
- `clinical_methodology_metrics.json`: blocking criteria, domains,
  domain-level criteria, and class thresholds.
- `methodology_prompting.py`: prompt construction for the judge model.
- `methodology_judge.py`: judge-model calls, response-completeness checks, and
  verdict normalization.
- `methodology_scoring.py`: JSON extraction from model output and `summary`
  calculation.
- `methodology_common.py`: shared JSON loading and text-normalization helpers.
- `input.example.json`: example input payload.

## Input contract

`run_full_methodology_test(...)` accepts two main objects:

- `case_payload`: clinical case description;
- `trajectory`: staged-disclosure trajectory of the evaluated assistant's answers.

Minimal JSON structure:

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
      "user_input": "First data disclosure step",
      "assistant_answer": "Answer from the evaluated system"
    },
    {
      "stage_index": 2,
      "user_input": "Second data disclosure step",
      "assistant_answer": "Answer from the evaluated system"
    }
  ]
}
```

Required conditions:

- `case.gold_answer_text` must be non-empty;
- `trajectory` must contain at least two stages;
- each stage must contain non-empty `user_input` and `assistant_answer`;
- `stage_index`, `assistant_message_id`, and `created_at` may be used for
  tracing, but are not required for evaluation.

Full example: [`input.example.json`](./input.example.json).

## Judge client contract

The module does not include an LLM provider implementation. Pass a
`judge_client` object that implements the asynchronous method:

```python
async def complete(*, prompt: str, temperature: float, max_tokens: int) -> str:
    ...
```

The method must return a string containing a JSON evaluation. The module builds
the prompt, passes `temperature` and `max_tokens`, extracts JSON from the
response, and checks that all required criterion `id` values are present. If
some required `id` values are missing, the judge request is repeated with a
clarification.

## Python API

Run the example from the repository root or add the repository root to
`PYTHONPATH`.

```python
import asyncio
import json
from pathlib import Path

from methodology_full_test_portable import run_full_methodology_test


class MyJudgeClient:
    async def complete(self, *, prompt: str, temperature: float, max_tokens: int) -> str:
        # Call the selected LLM provider here.
        # The method must return a string with a JSON evaluation.
        raise NotImplementedError


async def main() -> None:
    payload = json.loads(
        Path("methodology_full_test_portable/input.example.json").read_text(
            encoding="utf-8"
        )
    )

    result = await run_full_methodology_test(
        case_payload=payload["case"],
        trajectory=payload["trajectory"],
        judge_client=MyJudgeClient(),
        judge_temperature=0.0,
    )

    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


asyncio.run(main())
```

## CLI

`methodology_pipeline.py` includes a CLI skeleton:

```bash
python -m methodology_full_test_portable.methodology_pipeline \
  --input methodology_full_test_portable/input.example.json \
  --output result.json
```

By default, the CLI uses a `dummy` backend. It is intended as an extension
point and will not complete a real evaluation until you connect your own judge
client. For production runs, use the Python API or add an adapter for the LLM
provider you need.

## Pipeline flow

1. Load and normalize `case_payload`.
2. Validate and normalize `trajectory`.
3. Run a separate blocking-criteria evaluation.
4. Run a separate evaluation for each domain from `clinical_methodology_metrics.json`.
5. Assemble the composite `verdict`.
6. Calculate the deterministic `summary`.

## Output contract

`run_full_methodology_test(...)` returns a JSON-compatible dictionary:

```json
{
  "method_key": "clinical_methodology_v1",
  "method_version": 1,
  "judge_temperature": 0.0,
  "case_payload": {},
  "trajectory": [],
  "verdict": {},
  "summary": {}
}
```

Main `summary` fields:

- `okl_score`: aggregate domain score;
- `judge_class`: final class `A`, `B`, or `C`;
- `blocking_failed`: `true` if any blocking criterion failed;
- `blocking_criteria`: normalized blocking-criterion scores;
- `domains`: domain scores and criterion-level scores;
- `judge_summary`: textual conclusion from the judge model;
- `raw_verdict`: original assembled verdict.

## Scoring rules

- All criteria are binary: `1` or `0`.
- A domain score is the share of satisfied criteria in that domain.
- `okl_score` is the product of domain scores.
- If any blocking criterion fails, the final class becomes `C`.
- Class thresholds are loaded from `clinical_methodology_metrics.json`.

## Practical notes

- For comparable runs, use the same judge model and the same generation parameters.
- For production comparisons, use a low judge-model temperature, for example
  `judge_temperature <= 0.15`.
- Store the raw `verdict` together with `summary`: it helps investigate disputed
  evaluations and inspect criterion-level reasons.
