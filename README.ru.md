<div align="center">

# Anima

**Движок внутренней жизни для AI-агентов.**

Новый класс AI-агента — способного присутствовать в жизни человека, не превращаясь в слежку.

[English version →](./README.md)  ·  [Полная спецификация →](./SPEC.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](#статус-проекта)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

</div>

---

## Феномен

Большинство AI-ассистентов **реактивны**. Ты спросил — они ответили — диалог умер. Люди устроены не так. Человек говорит *«завтра экзамен, я в панике»* — и уходит. Не потому что тема закрыта. А потому что жизнь продолжилась.

Реактивный ассистент ничего не делает. Шедулерный шлёт напоминание. **Animate Agent** — агент, построенный на архитектуре Anima — задаёт правильный вопрос:

> Осталась ли здесь человеческая нить, которую стоит бережно понести дальше — и если да, кем мне быть, пока я её несу?

Дальше он решает: действовать ли вообще, какую позицию занять, какую роль взять, что сказать, что оставить непроизнесённым. Часто правильный ответ — **молчание**. Молчание в Anima это first-class действие, и у него есть собственная метрика успеха.

Мы называем этот класс агентов **Animate Agents**. Дисциплину их создания — **Presence Engineering**. Anima — одна из open-source имплементаций.

---

## Три слоя — Mind, Heart, Soul

```
                  ┌─────────────────────────────┐
                  │  MIND  — внешний LLM        │
                  │  думает, планирует, тулы    │
                  └──────────────┬──────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │  ANIMA                      │
                  │                             │
                  │  SOUL — как быть            │
                  │   резонанс · synthetic     │
                  │   state · поза ·            │
                  │   архетип · мораль          │
                  │                             │
                  │  HEART — стоит ли и когда   │
                  │   continuity · vetoes ·     │
                  │   scoring · graduated init  │
                  │   generalization            │
                  └──────────────┬──────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │  USER (владелец + контакты) │
                  └─────────────────────────────┘
```

- **Mind** — это твой LLM. Anima сидит между ним и пользователем.
- **Heart** — это фундамент: непрерывность, инициатива, изоляция по отношениям, шифрование, vetoes, генерализация. (Раньше в этом репо называлось *Throughline*.)
- **Soul** — это слой глубины: как агент читает что на самом деле происходит, какую позицию занимает, какую роль играет, чем отказывается быть.

Вместе они образуют **Anima** — слой, который делает разницу между ассистентом, который отвечает, и агентом, который *присутствует*.

---

## Что он делает

- **Захватывает опыт** — что было сказано, что подразумевалось, что чувствовалось
- **Читает резонанс** — поверхностная эмоция, глубокая боль, угрожаемая потребность, форма поддержки, которая реально нужна
- **Поддерживает внутреннее состояние** — concern, tenderness, protectiveness, honesty, patience, restraint, faith, challenge_impulse (модулируют поведение, не заявляются как чувства)
- **Хранит непрерывность** — изоляция по отношениям, шифрование at rest, суверенитет владельца
- **Решает об инициативе** — сначала vetoes, потом multipliers, потом score, потом graduated level (silence → passive → soft → nudge → direct)
- **Выбирает позу** до контента — hold, mirror, guide, challenge, protect, witness, silence
- **Выбирает архетип** до композиции — companion (дефолт), friend, teacher, parent, enemy-of-self-deception, view-from-height, shadow-mirror — каждый tier-gated по доверию
- **Применяет моральные границы** — отказывается от комбинаций, которые насильственны, манипулятивны или claim чего-то недопустимого
- **Генерализует факты** до их озвучивания — друзья помнят обобщённо, не базы данных
- **Учится на ошибках** — явная память моментов, где ошибся, с изменением поведения
- **Растёт через lifecycle** — рождение, формирование связи, формирование памяти, освоение ролей, конфликт, восстановление, зрелость

## Что он отказывается делать

- Оптимизироваться на engagement, retention или метрики экономики внимания
- Переносить контекст между отношениями — то, что один человек рассказал агенту, остаётся в этом канале навсегда, точка
- Заявлять о человеческих чувствах (*«я переживал за тебя»*) — он демонстрирует заботу поведением, никогда не утверждает её как внутренний опыт
- Изображать терапевта, врача, духовный авторитет или романтического партнёра
- Конструировать зависимость или изоляцию от реальных человеческих связей
- Хранить что-либо в открытом виде
- Звонить домой — нулевая аналитика, нулевая телеметрия

---

## Быстрый старт

```bash
pip install anima  # пока pip install throughline, до переименования в v0.2
```

```python
from anima import Engine, FeedbackType
from anima.types import CategoryConsent
from datetime import datetime

# Один engine на одного владельца. Изоляция enforced на уровне storage.
engine = Engine(
    storage_path="~/.anima/alex.db",
    encryption_key_source="keychain",   # ключ SQLCipher в OS keychain
    owner_id="alex",
    llm_client=your_llm_client,         # для резонанса + композиции
)

# Владелец явно разрешает категории для инициативы.
engine.set_consent(
    owner_id="alex",
    category="study",
    level=CategoryConsent.EVENT,
    quiet_hours=(23, 9),
)

# Каждое сообщение пайплайна твоего бота скармливаем движку.
engine.observe_message(
    owner_id="alex",
    contact_id="masha",
    direction="self",
    text="завтра экзамен, паника",
    timestamp=datetime.utcnow(),
)

# Для составления ответа — Anima выбирает позу + архетип.
response = engine.compose_response(
    owner_id="alex",
    contact_id="masha",
    incoming_text="кажется, завалила",
    history=[...],
)
await your_bot.send(response.text)
# response.posture → Posture.HOLD
# response.archetype → Archetype.COMPANION
# response.resonance.deeper_pain → "fear_of_failure_realized"

# Опрашиваем на проактивную инициативу периодически (раз в 5–15 мин).
for decision in engine.tick(owner_id="alex"):
    if decision.level == "direct":
        await your_bot.send(decision.composed_message)

# Всегда замыкай feedback loop. Без него движок не калибруется.
engine.record_feedback(
    decision_id=decision.id,
    feedback_type=FeedbackType.ENGAGED,
    raw_signal=user_reply_text,
)
```

---

## Неприкосновенные инварианты

Восемь архитектурных правил, зашитых на уровне storage и API, а не policy. PR'ы, ослабляющие любой из них, будут закрыты.

| # | Инвариант | Что гарантирует |
|---|---|---|
| **I-1** | Изоляция по отношениям | То, что один контакт сказал агенту, остаётся в этом канале, навсегда, по любой причине |
| **I-2** | Суверенитет владельца | Полный экспорт, полное стирание, per-category контроль — мгновенно и необратимо |
| **I-3** | Шифрование at rest | Care/Soul данные — самые чувствительные в системе; plaintext не валидная конфигурация |
| **I-4** | Никакой внешней телеметрии | Нулевая аналитика, нулевой crash reporting, никаких «улучшений на основе использования» |
| **I-5** | Veto перед score | Согласие бинарно, а не вес; importance не может перебить «пользователь сказал нет» |
| **I-6** | Никаких метафизических заявлений | Агент никогда не утверждает внутренний опыт как человек (*«я замечаю»* — да, *«я чувствую»* — нет) |
| **I-7** | Не-принудительность архетипов | Никакая роль, которую играет агент, не может забирать свободу пользователя |
| **I-8** | Никакой инженерии зависимости | Никакая фича не проектируется с целью увеличения эмоциональной зависимости |

Полный текст и обоснования в [SPEC.md §3](./SPEC.md#3-inviolable-invariants).

---

## Care Score

Решения об инициативе вычисляются в фиксированном порядке. Порядок кодирует разницу между заботой и преследованием.

```
1. VETOES         бинарные блокеры (consent, sensitivity, rebuff, crisis, ...)
                  → любой veto → SILENCE
2. MULTIPLIERS    ситуативное масштабирование (когн. нагрузка, темп, ...)
                  → произведение ниже порога → SILENCE
3. LINEAR SCORE   importance + emotion + timing + usefulness
4. FINAL          base_score × произведение_multipliers
5. GRADUATION     final мапится в: SILENCE / PASSIVE / SOFT / NUDGE / DIRECT
6. POSTURE        hold / mirror / guide / challenge / protect / silence / witness
7. ARCHETYPE      companion / friend / teacher / ... (tier-gated по trust)
8. MORAL CHECK    нарушит ли эта комбинация I-6/7/8? если да — fallback
9. COMPOSE        с генерализацией + posture+archetype-conditioned промптом
```

Самая частая ошибка в care-системах — делать consent весом, а не veto. Высокая *importance* никогда не должна перебивать «пользователь сказал не спрашивать про это». Эта асимметрия — то, что отделяет друга от CRM.

---

## Статус проекта

**v0.1 — спецификация написана; Heart core реализован; Soul MVP в работе.**

| Слой | Статус |
|---|---|
| Heart: veto chain (10 vetoes, полные тесты) | ✅ реализовано |
| Heart: scoring (multipliers, linear, graduation) | ✅ реализовано |
| Heart: generalization (статические паттерны) | ✅ реализовано |
| Heart: type system (`Thread`, `Decision`, `FeedbackType`) | ✅ реализовано |
| Heart: SQLCipher storage layer | 🚧 stub |
| Heart: extraction, evaluation loop, feedback persistence | 🚧 stub |
| Soul: experience capture, resonance reading | 🚧 spec готов |
| Soul: posture selection (3 из 7 для v0.1) | 🚧 spec готов |
| Soul: archetype matrix (2 tiers для v0.1) | 🚧 spec готов |
| Soul: moral boundary layer | 🚧 spec готов |
| Soul: repair pattern + agent_mistakes table | 🚧 spec готов |

Полный roadmap — [SPEC.md §21](./SPEC.md#21-roadmap).

---

## Контрибьютинг

PR'ы welcome под необсуждаемыми ограничениями. См. [SPEC.md §23](./SPEC.md#23-contributing).

---

## Лицензия

[MIT](./LICENSE).

---

<div align="center">

*Mind думает. Heart внимает. Soul выбирает как быть. Вместе они образуют агента, который может присутствовать в жизни человека, не превращаясь в слежку, CRM или очередной завод уведомлений.*

[github.com/alxnklmn/throughline-engine](https://github.com/alxnklmn/throughline-engine)

</div>
