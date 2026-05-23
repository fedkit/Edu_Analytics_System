# Student Analytics Dashboard

Полноценная аналитическая платформа для анализа поведения студентов университета (56 метрик).

## Быстрый запуск (3 команды)

```bash
git clone <repo-url>
cd CW_DB
docker-compose up --build
```

Открыть: http://localhost:3000

## Стек

- **Backend**: Python + FastAPI + SQLAlchemy
- **Database**: PostgreSQL 15
- **Frontend**: React 18 + Recharts
- **Infra**: Docker Compose

## Архитектура

```
db (PostgreSQL) ← backend (FastAPI + seed.py) ← frontend (React)
                ← simulator (real-time data generator)
```

## Сервисы

| Сервис    | Порт | Описание                    |
|-----------|------|-----------------------------|
| frontend  | 3000 | React SPA                   |
| backend   | 8000 | FastAPI (docs: /docs)       |
| db        | 5432 | PostgreSQL                  |
| simulator | —    | Real-time event generator   |

## Данные

- ~500 студентов ИУ МГТУ им. Баумана
- 12 кафедр (ИУ1–ИУ12)
- 4 образовательные программы
- ~30 предметов для IT-специальностей
- ~50,000 сессий за 12 месяцев
- Симулятор генерирует события в реальном времени

## API

Документация: http://localhost:8000/docs

### Блоки метрик

1. `/api/activity/*` — DAU/WAU/MAU, stickiness, retention, устройства
2. `/api/funnel/*` — воронки, drop-off, навигация
3. `/api/rfm/*` — RFM-сегментация, churn risk
4. `/api/academic/*` — pass rate, оценки, группы риска
5. `/api/correlation/*` — поведение vs успеваемость
6. `/api/comparison/*` — сравнение групп
7. `/api/temporal/*` — тепловые карты активности
8. `/api/predictive/*` — early warning, прогноз оценок
9. `/api/meta/*` — справочники и live-статистика
