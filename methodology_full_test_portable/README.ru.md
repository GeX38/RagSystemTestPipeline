# methodology_full_test_portable

Языки: [EN](./README.md) | [RU](./README.ru.md)

Обзор репозитория: [../README.md](../README.md)

Эта папка содержит переносимый модуль полной методики оценки медицинского
ИИ-помощника. Его можно использовать внутри этого репозитория или скопировать в
другой проект, если нужно запускать ту же оценку рядом с собственной системой.

## Назначение модуля

Модуль принимает клинический кейс и многошаговую траекторию диалога, вызывает
внешнюю judge-модель, приводит ее JSON-ответы к ожидаемой схеме и
детерминированно рассчитывает итоговую оценку.

Здесь описан технический контракт модуля. Верхнеуровневое описание методики,
границ применения и состава репозитория находится в корневом README.

## Состав файлов

- `methodology_pipeline.py`: публичная функция `run_full_methodology_test(...)`
  и минимальный CLI-каркас.
- `client_protocol.py`: протокол `JudgeModelProtocol`.
- `clinical_methodology_metrics.json`: blocking-критерии, домены, критерии
  внутри доменов и пороги классов.
- `methodology_prompting.py`: сборка prompt для judge-модели.
- `methodology_judge.py`: вызовы judge-модели, проверка полноты ответа и
  нормализация verdict.
- `methodology_scoring.py`: извлечение JSON из ответа модели и расчет `summary`.
- `methodology_common.py`: общие утилиты загрузки JSON и нормализации текста.
- `input.example.json`: пример входного payload.

## Входной контракт

Функция `run_full_methodology_test(...)` принимает два основных объекта:

- `case_payload`: описание клинического кейса;
- `trajectory`: staged-disclosure траектория ответов оцениваемого ассистента.

Минимальная структура JSON:

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
      "assistant_answer": "Ответ оцениваемой системы"
    },
    {
      "stage_index": 2,
      "user_input": "Второй шаг раскрытия данных",
      "assistant_answer": "Ответ оцениваемой системы"
    }
  ]
}
```

Обязательные условия:

- `case.gold_answer_text` должен быть непустым;
- `trajectory` должна содержать минимум два этапа;
- каждый этап должен содержать непустые `user_input` и `assistant_answer`;
- `stage_index`, `assistant_message_id` и `created_at` могут использоваться для
  трассировки, но не являются обязательными для оценки.

Полный пример: [`input.example.json`](./input.example.json).

## Контракт judge-клиента

Модуль не включает реализацию LLM-провайдера. Передайте объект `judge_client`,
который реализует асинхронный метод:

```python
async def complete(*, prompt: str, temperature: float, max_tokens: int) -> str:
    ...
```

Метод должен вернуть строку с JSON-оценкой. Модуль сам формирует prompt,
передает `temperature` и `max_tokens`, извлекает JSON из ответа и проверяет, что
в ответе присутствуют все обязательные `id` критериев. Если часть `id`
пропущена, запрос к judge-модели повторяется с уточнением.

## Python API

Запускайте пример из корня репозитория или добавьте корень репозитория в
`PYTHONPATH`.

```python
import asyncio
import json
from pathlib import Path

from methodology_full_test_portable import run_full_methodology_test


class MyJudgeClient:
    async def complete(self, *, prompt: str, temperature: float, max_tokens: int) -> str:
        # Здесь должен быть вызов выбранного LLM-провайдера.
        # Метод обязан вернуть строку с JSON-оценкой.
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

В `methodology_pipeline.py` есть CLI-каркас:

```bash
python -m methodology_full_test_portable.methodology_pipeline \
  --input methodology_full_test_portable/input.example.json \
  --output result.json
```

По умолчанию CLI использует `dummy` backend. Он предназначен как точка
расширения и не завершит реальную оценку без подключения собственного
judge-клиента. Для рабочих запусков удобнее использовать Python API или
добавить в CLI адаптер нужного LLM-провайдера.

## Что делает pipeline

1. Загружает и нормализует `case_payload`.
2. Валидирует и нормализует `trajectory`.
3. Запускает отдельную оценку blocking-критериев.
4. Запускает отдельную оценку каждого домена из `clinical_methodology_metrics.json`.
5. Собирает общий `verdict`.
6. Рассчитывает детерминированный `summary`.

## Выходной контракт

`run_full_methodology_test(...)` возвращает JSON-совместимый словарь:

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

Основные поля `summary`:

- `okl_score`: интегральный доменный балл;
- `judge_class`: итоговый класс `A`, `B` или `C`;
- `blocking_failed`: `true`, если провален хотя бы один blocking-критерий;
- `blocking_criteria`: нормализованные оценки blocking-критериев;
- `domains`: оценки доменов и критериев внутри них;
- `judge_summary`: текстовый итог judge-модели;
- `raw_verdict`: исходный собранный verdict.

## Правила расчета

- Все критерии бинарные: `1` или `0`.
- Доменный балл равен доле выполненных критериев домена.
- `okl_score` считается как произведение доменных баллов.
- Если провален любой blocking-критерий, итоговый класс становится `C`.
- Пороги классов берутся из `clinical_methodology_metrics.json`.

## Практические замечания

- Для сравнимых прогонов используйте одинаковую judge-модель и одинаковые
  параметры генерации.
- Для рабочих сравнений лучше использовать низкую температуру judge-модели,
  например `judge_temperature <= 0.15`.
- Сохраняйте сырой `verdict` вместе с `summary`: это помогает разбирать спорные
  оценки и проверять причины по каждому критерию.
