"""
simulator.py — непрерывная имитация активности студентов.

Пишет в:
  ClickHouse  edu_analytics.session  (часто)
              edu_analytics.event    (часто)
  PostgreSQL  edu.attendance         (редко,   ~5 % сессий)
              edu.score              (редко,   ~2 % сессий)
              edu.exam               (очень редко, ~0.2 % сессий)

Запуск:  python simulator.py
Стоп:    Ctrl+C
"""

import random
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
from clickhouse_driver import Client

random.seed()  # не фиксируем — каждый запуск уникален

PG_DSN  = "postgresql://fedor@/university_db?host=/var/run/postgresql"
CH_HOST = "localhost"

# ── Вероятности побочных действий за одну сессию ──
P_ATTENDANCE = 0.05
P_SCORE      = 0.02
P_EXAM       = 0.002

# ── Конфиг сессий/событий ─────────────────────────
EVENTS_PER_SESSION = (3, 20)
SESSION_DURATION   = (5, 90)   # минуты

DEVICE_TYPES   = ["mobile", "desktop", "tablet"]
DEVICE_WEIGHTS = [0.45, 0.45, 0.10]

SECTION_PURPOSE = {
    "home":     ["navigation", "search"],
    "course":   ["learning", "download"],
    "exam":     ["exam_prep", "grade_check"],
    "profile":  ["profile_view"],
    "library":  ["learning", "download", "search"],
    "schedule": ["schedule"],
    "grades":   ["grade_check"],
}
SECTION_EVENT_TYPES = {
    "home":     (["view", "navigate", "click"],  [0.4, 0.4, 0.2]),
    "course":   (["view", "scroll", "click"],    [0.3, 0.4, 0.3]),
    "exam":     (["view", "click", "submit"],    [0.4, 0.4, 0.2]),
    "profile":  (["view", "click"],              [0.6, 0.4]),
    "library":  (["view", "scroll", "click"],    [0.3, 0.5, 0.2]),
    "schedule": (["view", "navigate"],           [0.6, 0.4]),
    "grades":   (["view", "scroll"],             [0.5, 0.5]),
}
SECTION_WEIGHTS = {
    "course": 0.35, "grades": 0.20, "exam": 0.15,
    "schedule": 0.10, "home": 0.08, "profile": 0.07, "library": 0.05,
}
ELEMENT_NAMES = (
    [f"btn_{i}" for i in range(1, 15)] +
    ["link_nav", "link_back", "menu_item", "card",
     "tab", "form_submit", "dropdown", "search_input",
     "filter", "pagination", "breadcrumb"]
)

LESSON_TYPES = ["лекция", "практика", "лабораторная"]
SCORE_TYPES  = ["РК", "ДЗ", "лаб", "итог"]
EXAM_TYPES   = ["письменный", "устный", "тест"]
PASSED_TYPES = ["зачёт", "экзамен", "дифзачёт"]


# ─────────────────────────────────────────────────
# Загрузка справочников из PostgreSQL
# ─────────────────────────────────────────────────

def load_reference_data(pg):
    cur = pg.cursor()

    # Пользователи — только активные (Обучается)
    cur.execute("""
        SELECT user_id, status
        FROM edu."user"
        WHERE status IN ('Обучается', 'Академический отпуск')
        ORDER BY user_id
    """)
    users = cur.fetchall()   # [(user_id, status), ...]

    # Предметы пользователя: user_id → [subject_id, ...]
    cur.execute("SELECT user_id, subject_id FROM edu.user_subject")
    user_subjects: dict = defaultdict(list)
    for uid, sid in cur.fetchall():
        user_subjects[uid].append(sid)

    # Все предметы
    cur.execute("SELECT subject_id FROM edu.subject")
    all_subjects = [r[0] for r in cur.fetchall()]
    subject_max  = {sid: 100 for sid in all_subjects}  # default max_score=100

    # Страницы
    cur.execute("SELECT page_id, page_section FROM edu.page")
    pages = cur.fetchall()   # [(page_id, section), ...]

    cur.close()
    return users, user_subjects, subject_max, pages


# ─────────────────────────────────────────────────
# Получение следующих ID
# ─────────────────────────────────────────────────

class IDCounter:
    """Простой счётчик, инициализируется из БД."""
    def __init__(self, start: int):
        self._val = start

    def next(self) -> int:
        self._val += 1
        return self._val


def init_counters(pg, ch):
    cur = pg.cursor()

    cur.execute("SELECT COALESCE(MAX(score_id), 0) FROM edu.score")
    score_start = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(MAX(attendance_id), 0) FROM edu.attendance")
    att_start = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(MAX(exam_id), 0) FROM edu.exam")
    exam_start = cur.fetchone()[0]

    cur.close()

    # ClickHouse
    sess_start  = ch.execute("SELECT COALESCE(MAX(session_id), 0) FROM edu_analytics.session")[0][0]
    event_start = ch.execute("SELECT COALESCE(MAX(event_id),   0) FROM edu_analytics.event")[0][0]

    return (
        IDCounter(sess_start),
        IDCounter(event_start),
        IDCounter(score_start),
        IDCounter(att_start),
        IDCounter(exam_start),
    )


# ─────────────────────────────────────────────────
# Генерация одной сессии + события
# ─────────────────────────────────────────────────

def simulate_session(user_id, pages_by_section, all_page_ids, sess_ctr, evt_ctr):
    now      = datetime.now()
    duration = timedelta(minutes=random.randint(*SESSION_DURATION))
    end_time = now + duration
    device   = random.choices(DEVICE_TYPES, weights=DEVICE_WEIGHTS, k=1)[0]

    session_id = sess_ctr.next()
    session_row = {
        "session_id":    session_id,
        "user_id":       user_id,
        "session_start": now,
        "session_end":   end_time,
        "device_type":   device,
    }

    sections    = list(SECTION_WEIGHTS.keys())
    sec_weights = list(SECTION_WEIGHTS.values())
    cur_section = random.choices(sections, weights=sec_weights, k=1)[0]
    cur_page    = random.choice(pages_by_section.get(cur_section, all_page_ids))
    event_time  = now + timedelta(seconds=random.randint(2, 20))

    events = []
    for _ in range(random.randint(*EVENTS_PER_SESSION)):
        if event_time >= end_time:
            break

        if random.random() < 0.30:
            cur_section = random.choices(sections, weights=sec_weights, k=1)[0]

        next_page = (
            random.choice(pages_by_section.get(cur_section, all_page_ids))
            if random.random() > 0.25 else None
        )
        evt_types, evt_w = SECTION_EVENT_TYPES.get(
            cur_section, (["view", "click"], [0.5, 0.5]))
        purposes = SECTION_PURPOSE.get(cur_section, ["navigation"])

        events.append({
            "event_id":     evt_ctr.next(),
            "page_id":      cur_page,
            "next_page_id": next_page,
            "session_id":   session_id,
            "event_time":   event_time,
            "event_type":   random.choices(evt_types, weights=evt_w, k=1)[0],
            "element_name": random.choice(ELEMENT_NAMES),
            "purpose":      random.choice(purposes),
        })

        event_time += timedelta(seconds=random.randint(5, 180))
        if next_page:
            cur_page = next_page
            # Обновляем секцию по следующей странице (ищем в индексе)
            # pages_by_section уже dict section→[page_ids], нужен обратный
        # (обратный индекс передаётся снаружи как page_section)

    return session_row, events


# ─────────────────────────────────────────────────
# PostgreSQL: запись attendance
# ─────────────────────────────────────────────────

def write_attendance(pg, att_ctr, user_id, user_subjects, subject_max):
    subjects = user_subjects.get(user_id)
    if not subjects:
        return False

    subject_id  = random.choice(subjects)
    lesson_date = datetime.now().date() - timedelta(days=random.randint(0, 30))
    lesson_time = f"{random.randint(8, 18):02d}:{random.choice(['00','30'])}:00"
    att_id      = att_ctr.next()

    try:
        cur = pg.cursor()
        cur.execute("""
            INSERT INTO edu.attendance
                (attendance_id, user_id, subject_id, lesson_date, lesson_time,
                 lesson_type, is_present)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (att_id, user_id, subject_id, lesson_date, lesson_time,
              random.choice(LESSON_TYPES),
              random.random() > 0.15))
        pg.commit()
        cur.close()
        return True
    except Exception as e:
        pg.rollback()
        print(f"  [att error] {e}")
        return False


# ─────────────────────────────────────────────────
# PostgreSQL: запись score
# ─────────────────────────────────────────────────

def write_score(pg, score_ctr, user_id, user_subjects, subject_max):
    subjects = user_subjects.get(user_id)
    if not subjects:
        return False

    subject_id  = random.choice(subjects)
    max_sc      = subject_max.get(subject_id, 100)
    score_val   = random.randint(int(max_sc * 0.4), max_sc)
    is_passed   = score_val >= max_sc * 0.6
    score_id    = score_ctr.next()

    try:
        cur = pg.cursor()
        cur.execute("""
            INSERT INTO edu.score
                (score_id, user_id, subject_id, score, max_score,
                 score_date, score_type, attempt_number, is_passed, module)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (score_id, user_id, subject_id, score_val, max_sc,
              datetime.now().date(),
              random.choice(SCORE_TYPES),
              1,
              is_passed,
              random.randint(1, 3)))
        pg.commit()
        cur.close()
        return True
    except Exception as e:
        pg.rollback()
        print(f"  [score error] {e}")
        return False


# ─────────────────────────────────────────────────
# PostgreSQL: запись exam (новый экзамен)
# ─────────────────────────────────────────────────

def write_exam(pg, exam_ctr, subject_max):
    if not subject_max:
        return False

    subject_id = random.choice(list(subject_max.keys()))
    exam_id    = exam_ctr.next()
    exam_date  = (datetime.now() + timedelta(days=random.randint(1, 60))).date()
    exam_time  = f"{random.randint(8, 18):02d}:00:00"

    try:
        cur = pg.cursor()
        cur.execute("""
            INSERT INTO edu.exam
                (exam_id, subject_id, exam_date, exam_time, exam_type, passed_type)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (exam_id, subject_id, exam_date, exam_time,
              random.choice(EXAM_TYPES),
              random.choice(PASSED_TYPES)))
        pg.commit()
        cur.close()
        return True
    except Exception as e:
        pg.rollback()
        print(f"  [exam error] {e}")
        return False


# ─────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────

def main():
    print("Подключаемся к базам данных …")
    pg = psycopg2.connect(PG_DSN)
    ch = Client(CH_HOST)
    print("  PostgreSQL OK | ClickHouse OK")

    print("Загружаем справочники …")
    users, user_subjects, subject_max, pages = load_reference_data(pg)
    print(f"  users: {len(users)}, subjects: {len(subject_max)}, pages: {len(pages)}")

    # Индексы страниц
    pages_by_section: dict = defaultdict(list)
    page_section_map: dict = {}
    for pid, sec in pages:
        pages_by_section[sec].append(pid)
        page_section_map[pid] = sec
    all_page_ids = [p[0] for p in pages]

    print("Инициализируем счётчики ID …")
    sess_ctr, evt_ctr, score_ctr, att_ctr, exam_ctr = init_counters(pg, ch)
    print(f"  next session_id={sess_ctr._val+1}, event_id={evt_ctr._val+1}")

    # Статистика
    stats = {"sessions": 0, "events": 0, "attendance": 0, "scores": 0, "exams": 0}
    start_time = time.time()
    last_print = start_time

    print("\nСимулятор запущен. Нажмите Ctrl+C для остановки.\n")

    def shutdown(sig, frame):
        elapsed = time.time() - start_time
        print(f"\n\nОстановлено. За {elapsed:.0f} с записано:")
        for k, v in stats.items():
            print(f"  {k:<12} {v:>8,}")
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Активные пользователи — весовой выбор по статусу
    active_users = [u for u in users if u[1] == "Обучается"]
    other_users  = [u for u in users if u[1] != "Обучается"]
    user_pool    = active_users + other_users   # активные доминируют числом

    while True:
        user_id, status = random.choice(user_pool)

        # ── Генерируем сессию и события ───────────
        sess_row, events = simulate_session(
            user_id, pages_by_section, all_page_ids, sess_ctr, evt_ctr)

        try:
            ch.execute(
                "INSERT INTO edu_analytics.session "
                "(session_id, user_id, session_start, session_end, device_type) VALUES",
                [sess_row],
            )
            if events:
                ch.execute(
                    "INSERT INTO edu_analytics.event "
                    "(event_id, page_id, next_page_id, session_id, "
                    " event_time, event_type, element_name, purpose) VALUES",
                    events,
                )
        except Exception as e:
            print(f"  [CH error] {e}")
            time.sleep(2)
            continue

        stats["sessions"] += 1
        stats["events"]   += len(events)

        # ── Редкие академические события ──────────
        if random.random() < P_ATTENDANCE:
            if write_attendance(pg, att_ctr, user_id, user_subjects, subject_max):
                stats["attendance"] += 1

        if random.random() < P_SCORE:
            if write_score(pg, score_ctr, user_id, user_subjects, subject_max):
                stats["scores"] += 1

        if random.random() < P_EXAM:
            if write_exam(pg, exam_ctr, subject_max):
                stats["exams"] += 1

        # ── Периодический вывод статистики ────────
        now = time.time()
        if now - last_print >= 10:
            elapsed = now - start_time
            rate    = stats["sessions"] / elapsed if elapsed > 0 else 0
            print(
                f"[{elapsed:6.0f}s]  "
                f"sessions={stats['sessions']:,}  "
                f"events={stats['events']:,}  "
                f"att={stats['attendance']}  "
                f"scores={stats['scores']}  "
                f"exams={stats['exams']}  "
                f"({rate:.1f} sess/s)"
            )
            last_print = now

        # Небольшая пауза, чтобы не нагружать CPU
        time.sleep(random.uniform(0.05, 0.3))


if __name__ == "__main__":
    main()
