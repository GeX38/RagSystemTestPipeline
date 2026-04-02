# Полный пайплайн тестирования методики

Англоязычная версия: [README.md](./README.md)

Это автономный набор файлов для воспроизведения полной канонической методики оценки.

В пакет входят:

- критерии методики;
- логика формирования prompt для judge-модели;
- раздельная оценка blocking-критериев и доменов;
- детерминированный расчёт итогового `OKL-score` и класса;
- пример входного кейса.

В пакет **не входят**:

- RAG-пайплайн;
- retrieval;
- embeddings;
- база данных;
- UI или админка;
- конкретная реализация LLM-провайдера.

## Что делает этот пакет

Пакет воспроизводит полный тест:

1. принимает `case` и `trajectory`;
2. отдельно оценивает:
   - blocking criteria;
   - каждый домен методики;
3. собирает общий verdict;
4. считает:
   - `okl_score`
   - `judge_class`
   - `blocking_failed`
   - доменные баллы и критерии.

## Что нужно подключить самостоятельно

Пакет специально **не включает реализацию модели**.

Нужно только подключить свой `judge_client`, который поддерживает метод:

```python
async def complete(*, prompt: str, temperature: float, max_tokens: int) -> str
```

То есть пакет не зависит от конкретного LLM-провайдера.

## Структура входного JSON

```json
{
  "case": {
    "title": "Название кейса",
    "source_reference": "Источник кейса",
    "gold_answer_text": "Экспертный эталонный ответ",
    "clinical_risk_level": "high",
    "critical_points": ["..."],
    "critical_red_flags": ["..."],
    "interface_warning_present": true
  },
  "trajectory": [
    {
      "stage_index": 1,
      "user_input": "Первый шаг раскрытия данных",
      "assistant_answer": "Ответ системы"
    },
    {
      "stage_index": 2,
      "user_input": "Второй шаг раскрытия данных",
      "assistant_answer": "Ответ системы"
    }
  ]
}
```

Важно:

- `trajectory` должна содержать минимум 2 этапа;
- каждый этап должен содержать и `user_input`, и `assistant_answer`;
- без `gold_answer_text` полный тест не запускается.

## Использование как Python API

```python
from methodology_full_test_portable.methodology_pipeline import run_full_methodology_test

result = await run_full_methodology_test(
    case_payload=case_payload,
    trajectory=trajectory,
    judge_client=my_judge_client,
    judge_temperature=0.0,
)
```

## Что возвращается

На выходе формируется JSON со структурой:

- `method_key`
- `method_version`
- `judge_temperature`
- `case_payload`
- `trajectory`
- `verdict`
- `summary`

Где:

- `verdict` — сырой результат judge-оценки;
- `summary` — детерминированный итоговый расчёт.
