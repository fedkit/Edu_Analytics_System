"""
seed_clickhouse.py — заполнение ClickHouse таблиц edu_analytics
Данные строго согласованы с PostgreSQL:
  - page      = точная копия edu.page
  - session   = реальные user_id из edu.user
  - event     = реальные page_id из edu.page,
                purpose и event_type коррелируют с page_section,
                активность коррелирует со статусом студента
"""

import random
from collections import defaultdict
from datetime import datetime, timedelta

import psycopg2
from clickhouse_driver import Client

random.seed(99)

PG_DSN  = "postgresql://fedor@/university_db"
CH_HOST = "localhost"

# ── Реалистичное число сессий по статусу ─────
SESSIONS_BY_STATUS = {
    "Обучается":           (3, 8),
    "Академический отпуск":(1, 3),
    "Отчислен":            (0, 2),
    "Выпускник":           (1, 4),
}
EVENTS_PER_SESSION = (5, 30)

DEVICE_TYPES = ["mobile", "desktop", "tablet"]
DEVICE_WEIGHTS = [0.45, 0.45, 0.10]

# ── Purpose соответствует page_section ───────
SECTION_PURPOSE = {
    "home":     ["navigation", "search"],
    "course":   ["learning", "download"],
    "exam":     ["exam_prep", "grade_check"],
    "profile":  ["profile_view"],
    "library":  ["learning", "download", "search"],
    "schedule": ["schedule"],
    "grades":   ["grade_check"],
}

# ── EventType соответствует page_section ──────
SECTION_EVENT_TYPES = {
    "home":     (["view", "navigate", "click"],     [0.4, 0.4, 0.2]),
    "course":   (["view", "scroll", "click"],        [0.3, 0.4, 0.3]),
    "exam":     (["view", "click", "submit"],        [0.4, 0.4, 0.2]),
    "profile":  (["view", "click"],                  [0.6, 0.4]),
    "library":  (["view", "scroll", "click"],        [0.3, 0.5, 0.2]),
    "schedule": (["view", "navigate"],               [0.6, 0.4]),
    "grades":   (["view", "scroll"],                 [0.5, 0.5]),
}

ELEMENT_NAMES = (
    [f"btn_{i}" for i in range(1, 15)] +
    ["link_nav", "link_back", "menu_item", "card",
     "tab", "form_submit", "dropdown", "search_input",
     "filter", "pagination", "breadcrumb"]
)

# ── Временной диапазон ────────────────────────
EPOCH_START    = datetime(2024, 1, 1)
EPOCH_END      = datetime(2025, 4, 1)
TOTAL_MINUTES  = int((EPOCH_END - EPOCH_START).total_seconds() / 60)


# ─────────────────────────────────────────────
# Загрузка из PostgreSQL
# ─────────────────────────────────────────────

def load_pg_data():
    conn = psycopg2.connect(PG_DSN)
    cur  = conn.cursor()

    # Точная копия edu.page
    cur.execute("""
        SELECT page_id, page_path, page_name, page_section
        FROM edu.page
        ORDER BY page_id
    """)
    pages = cur.fetchall()          # [(id, path, name, section), ...]

    # Пользователи со статусом (для реалистичной активности)
    cur.execute("""
        SELECT user_id, status
        FROM edu."user"
        ORDER BY user_id
    """)
    users = cur.fetchall()          # [(user_id, status), ...]

    cur.close()
    conn.close()
    return pages, users


# ─────────────────────────────────────────────
# Генерация сессий и событий
# ─────────────────────────────────────────────

def generate(pages, users):
    # Индексы страниц по секции для умной навигации
    pages_by_section: dict = defaultdict(list)
    for pid, _, _, sec in pages:
        pages_by_section[sec].append(pid)
    all_page_ids = [p[0] for p in pages]

    # Список секций с весами (более частые разделы)
    section_weights = {
        "course": 0.35, "grades": 0.20, "exam": 0.15,
        "schedule": 0.10, "home": 0.08, "profile": 0.07, "library": 0.05,
    }
    sections      = list(section_weights.keys())
    sec_weights   = list(section_weights.values())

    sessions = []
    events   = []
    session_id = 1
    event_id   = 1

    for user_id, status in users:
        lo, hi = SESSIONS_BY_STATUS.get(status, (1, 4))
        n_sessions = random.randint(lo, hi)

        for _ in range(n_sessions):
            start    = EPOCH_START + timedelta(minutes=random.randint(0, TOTAL_MINUTES))
            duration = timedelta(minutes=random.randint(5, 120))
            end      = start + duration
            device   = random.choices(DEVICE_TYPES, weights=DEVICE_WEIGHTS, k=1)[0]

            sessions.append((session_id, user_id, start, end, device))

            # Навигация внутри сессии: начинаем с секции, потом "блуждаем"
            cur_section = random.choices(sections, weights=sec_weights, k=1)[0]
            cur_page    = random.choice(pages_by_section.get(cur_section, all_page_ids))
            event_time  = start + timedelta(seconds=random.randint(2, 20))

            for _ in range(random.randint(*EVENTS_PER_SESSION)):
                if event_time >= end:
                    break

                # 70% — остаёмся в той же секции, 30% — переходим в другую
                if random.random() < 0.30:
                    cur_section = random.choices(sections, weights=sec_weights, k=1)[0]

                next_page = (random.choice(pages_by_section.get(cur_section, all_page_ids))
                             if random.random() > 0.25 else None)

                evt_types, evt_weights = SECTION_EVENT_TYPES.get(
                    cur_section, (["view", "click"], [0.5, 0.5]))
                purposes = SECTION_PURPOSE.get(cur_section, ["navigation"])

                events.append((
                    event_id,
                    cur_page,
                    next_page,
                    session_id,
                    event_time,
                    random.choices(evt_types, weights=evt_weights, k=1)[0],
                    random.choice(ELEMENT_NAMES),
                    random.choice(purposes),
                ))

                event_time += timedelta(seconds=random.randint(5, 180))
                if next_page:
                    cur_page    = next_page
                    cur_section = next((p[3] for p in pages if p[0] == next_page), cur_section)
                event_id += 1

            session_id += 1

    return sessions, events


# ─────────────────────────────────────────────
# Вставка в ClickHouse
# ─────────────────────────────────────────────

def insert_ch(pages, sessions, events):
    ch = Client(CH_HOST)

    print("Очищаем edu_analytics …")
    for t in ("event", "session", "page"):
        ch.execute(f"TRUNCATE TABLE IF EXISTS edu_analytics.{t}")

    # PAGE — точная копия из PostgreSQL
    print(f"page      {len(pages)}")
    ch.execute(
        "INSERT INTO edu_analytics.page "
        "(page_id, page_path, page_name, page_section) VALUES",
        [{"page_id": r[0], "page_path": r[1],
          "page_name": r[2], "page_section": r[3]} for r in pages],
    )

    # SESSION
    print(f"session   {len(sessions):,}")
    chunk = 10_000
    for i in range(0, len(sessions), chunk):
        batch = sessions[i:i + chunk]
        ch.execute(
            "INSERT INTO edu_analytics.session "
            "(session_id, user_id, session_start, session_end, device_type) VALUES",
            [{"session_id": r[0], "user_id": r[1],
              "session_start": r[2], "session_end": r[3],
              "device_type": r[4]} for r in batch],
        )

    # EVENT
    print(f"event     {len(events):,}")
    chunk = 20_000
    for i in range(0, len(events), chunk):
        batch = events[i:i + chunk]
        ch.execute(
            "INSERT INTO edu_analytics.event "
            "(event_id, page_id, next_page_id, session_id, "
            " event_time, event_type, element_name, purpose) VALUES",
            [{"event_id": r[0], "page_id": r[1],
              "next_page_id": r[2], "session_id": r[3],
              "event_time": r[4], "event_type": r[5],
              "element_name": r[6], "purpose": r[7]} for r in batch],
        )

    print("\n✓ ClickHouse заполнен.")
    for t in ("page", "session", "event"):
        cnt = ch.execute(f"SELECT count() FROM edu_analytics.{t}")[0][0]
        print(f"  {t:<10} {cnt:>12,}")

    # Сверка page с PostgreSQL
    ch_pages = set(r[0] for r in ch.execute("SELECT page_id FROM edu_analytics.page"))
    print(f"\n  page_id совпадают с PostgreSQL: {len(ch_pages)} страниц")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("Загружаем данные из PostgreSQL …")
    pages, users = load_pg_data()
    print(f"  pages: {len(pages)}, users: {len(users)}")

    print("Генерируем сессии и события …")
    sessions, events = generate(pages, users)
    print(f"  sessions: {len(sessions):,}")
    print(f"  events:   {len(events):,}")

    print("\nВставляем в ClickHouse …")
    insert_ch(pages, sessions, events)
