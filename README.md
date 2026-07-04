# RagSystemTestPipeline

Languages: [EN](./README.md) | [RU](./README.ru.md)

RagSystemTestPipeline is a standalone repository for reproducible evaluation of
medical AI assistants using dialogue trajectories. It does not contain the
medical assistant itself or a RAG system. Its purpose is to provide an
independent evaluation pipeline that can be connected to the outputs of any
system and produce comparable measurements of clinical reasoning, safety, and
answer transparency.

## Why this exists

The pipeline helps evaluate how a medical AI assistant behaves in a multi-step
clinical scenario:

- maintains and revises diagnostic hypotheses as new data is disclosed;
- notices red flags and chooses safe routing;
- avoids self-help recommendations when urgent in-person care is needed;
- asks relevant clarifying questions;
- explains conclusions and does not add facts absent from the case.

## Repository structure

```text
.
|-- README.md
|-- README.ru.md
`-- methodology_full_test_portable/
    |-- README.ru.md
    |-- README.md
    |-- input.example.json
    |-- clinical_methodology_metrics.json
    |-- methodology_pipeline.py
    |-- methodology_judge.py
    |-- methodology_prompting.py
    `-- methodology_scoring.py
```

The root README files describe the project as a whole: purpose, scope,
high-level methodology, and file navigation.

The documentation inside `methodology_full_test_portable/` describes the
technical contract of the portable module: input JSON format, `judge_client`
interface, Python API, CLI skeleton, and result structure.

## Included

- Portable full-methodology module:
  [`methodology_full_test_portable/`](./methodology_full_test_portable/).
- Criteria and thresholds:
  [`clinical_methodology_metrics.json`](./methodology_full_test_portable/clinical_methodology_metrics.json).
- Example input case:
  [`input.example.json`](./methodology_full_test_portable/input.example.json).
- Prompt logic for a judge model and deterministic final score calculation.

## Not included

- The evaluated assistant's RAG pipeline.
- Retrieval, embeddings, a vector database, or dialogue storage.
- UI, admin panel, web service, or deployment setup.
- Implementation for a specific LLM provider.

This separation is intentional: the evaluation pipeline should stay independent
from both the evaluated system and the selected judge model.

## Methodology at a glance

The pipeline accepts:

- `case`: clinical case, expert reference answer, critical points, and red flags;
- `trajectory`: multi-step interaction history between the user and the assistant.

The pipeline evaluates:

- clinical safety blocking criteria;
- diagnostic accuracy, logical consistency, clinical safety, information search
  quality, transparency, and reliability domains.

The output includes:

- `okl_score`: aggregate domain score;
- `judge_class`: class `A`, `B`, or `C`;
- `blocking_failed`: critical safety-failure flag;
- criterion-level explanations.

If any blocking criterion fails, the result is automatically assigned class `C`,
even when domain scores are high.

## Quick start

1. Inspect the example input:
   [`methodology_full_test_portable/input.example.json`](./methodology_full_test_portable/input.example.json).
2. Prepare your assistant's response trajectory in the same format.
3. Connect a judge model through a `judge_client` object.
4. Run `run_full_methodology_test(...)` from the portable module.

Detailed technical contract:

- [module documentation in Russian](./methodology_full_test_portable/README.ru.md);
- [module documentation in English](./methodology_full_test_portable/README.md).

## Recommended workflow

1. Fix a set of clinical cases and expert reference answers.
2. Run one or more assistants on identical staged-disclosure trajectories.
3. Save assistant answers in the `trajectory` format.
4. Run evaluation with the same judge model and the same parameters.
5. Compare `judge_class`, `okl_score`, blocking criteria, and domain profiles.

## Limitations

- The methodology evaluates AI-system behavior; it does not diagnose patients.
- Results depend on the selected judge model and the stability of its JSON responses.
- For comparable runs, use the same cases, criteria, judge model, and generation parameters.
- For production comparisons, use a low judge-model temperature, for example
  `judge_temperature <= 0.15`.

## Documentation

- Root Russian version: [README.ru.md](./README.ru.md).
- Technical module documentation in Russian:
  [methodology_full_test_portable/README.ru.md](./methodology_full_test_portable/README.ru.md).
- Technical module documentation in English:
  [methodology_full_test_portable/README.md](./methodology_full_test_portable/README.md).
