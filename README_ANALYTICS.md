# Electronic University Analytics Platform

Полноценная аналитическая платформа для анализа поведения студентов и академической успеваемости. Объединяет данные из PostgreSQL (академическая база) и ClickHouse (поведенческие события).

## Быстрый старт

```bash
cd /home/fedor/CW_DB

# Установка зависимостей
pip install -r requirements.txt

# Конфигурация (при необходимости отредактировать)
cp .env.example .env

# Запуск дашборда
streamlit run app/main.py
```

Откроется в браузере: **http://localhost:8501**

## Стек

| Слой        | Технология                          |
|-------------|--------------------------------------|
| Frontend    | Streamlit 1.35 + Plotly 5.22         |
| Backend     | Python 3.12                          |
| OLTP DB     | PostgreSQL 14 (схема `edu`)          |
| OLAP DB     | ClickHouse (база `edu_analytics`)    |
| ORM         | SQLAlchemy 2.0                       |
| Data        | Pandas 2.2 + NumPy                   |
| Stats       | SciPy + scikit-learn                 |
| Config      | Pydantic Settings + python-dotenv    |

## Страницы

| Страница            | Описание                                                     |
|---------------------|--------------------------------------------------------------|
| 📊 Дашборд          | KPI-карточки + тренды DAU, GPA, посещаемости, pass rate      |
| 🔍 Поведение        | Сессии, события, тепловые карты, устройства, навигация       |
| 🎯 Воронки          | Конструктор воронок по секциям, конверсия, drop-off          |
| 🔄 Retention        | Когортный анализ, матрица удержания                          |
| 📌 Stickiness       | DAU/WAU/MAU, stickiness-фактор по времени                    |
| 🎲 RFM              | Сегментация студентов: Champions, At Risk, Dropouts и др.    |
| 🎓 Академика        | GPA, посещаемость, экзамены — тренды и сравнения             |
| 🔗 Корреляции       | Поведение vs успеваемость, матрица корреляций, инсайты       |
| 👤 Профиль студента | Полная хронология студента: оценки, посещения, сессии        |
| ⚠️ Риски            | Группы риска, неактивные, падение GPA, риск отчисления       |

## Архитектура

```
app/
├── main.py                    # Streamlit entry point
├── config.py                  # Pydantic Settings
├── database/
│   ├── postgres.py            # SQLAlchemy engine
│   └── clickhouse.py          # clickhouse-connect client
├── repositories/
│   ├── academic_repo.py       # все запросы к PostgreSQL
│   └── behavior_repo.py       # все запросы к ClickHouse
├── services/
│   ├── rfm_service.py         # RFM-сегментация
│   ├── retention_service.py   # когортный анализ
│   ├── correlation_service.py # корреляционный анализ
│   ├── trend_service.py       # скользящие средние, тренды
│   └── funnel_service.py      # воронки
├── analytics/
│   ├── kpi.py                 # KPI-датаклассы
│   └── anomaly.py             # обнаружение аномалий (z-score)
├── components/
│   ├── filters.py             # глобальный сайдбар
│   ├── kpi_card.py            # карточки метрик
│   └── charts.py              # фабрика Plotly-графиков
└── pages/                     # по одному файлу на каждую страницу
```

## Фильтры (глобальные)

- **Период**: 7/30/90 дней, текущий/прошлый семестр, произвольный
- **Гранулярность**: день / неделя / месяц
- **Сравнение**: текущий vs предыдущий период
- **Факультет / группа / предмет / статус / устройство**
- **🔄 Обновить данные** — инвалидирует весь кэш

## Симулятор (real-time)

```bash
python simulator.py   # генерирует события непрерывно, Ctrl+C для стопа
```
