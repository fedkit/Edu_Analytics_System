"""
seed.py — заполнение PostgreSQL МГТУ им. Баумана
"""

import random
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from datetime import date, time, timedelta
from collections import defaultdict

random.seed(42)
np.random.seed(42)

DB_DSN = "postgresql://fedor@/university_db"
N_USERS = 30_000
SUBJECTS_PER_PROG   = (5, 10)
SCORES_PER_SUBJECT  = (3, 8)
LESSONS_PER_SUBJECT = (12, 30)

# ── Степени ──────────────────────────────────
DEGREE_NAMES    = ["Бакалавриат", "Магистратура", "Специалитет", "Аспирантура"]
FORM_NAMES      = ["Очная", "Заочная", "Очно-заочная"]
DEGREE_MAX_SEM  = {"Бакалавриат": 8, "Специалитет": 10, "Магистратура": 4, "Аспирантура": 8}
DEGREE_SUFFIX   = {"Бакалавриат": "Б", "Специалитет": "",  "Магистратура": "М", "Аспирантура": "А"}
DEGREE_YEARS    = {"Бакалавриат": 4,  "Специалитет": 5,   "Магистратура": 2,  "Аспирантура": 4}
DEGREE_AREA     = {"Бакалавриат": "03", "Специалитет": "05", "Магистратура": "04", "Аспирантура": "06"}

# ── Факультеты ────────────────────────────────
FACULTY_DATA = [
    ("ИУ",  "Информатика и системы управления",          "u"),
    ("ИБМ", "Инженерный бизнес и менеджмент",            "i"),
    ("МТ",  "Машиностроительные технологии",             "m"),
    ("СМ",  "Специальное машиностроение",                "s"),
    ("ПИШ", "Передовая инженерная школа",                "p"),
    ("БМТ", "Биомедицинская техника",                    "b"),
    ("РЛ",  "Радиоэлектроника и лазерная техника",       "l"),
    ("Э",   "Энергомашиностроение",                      "e"),
    ("РК",  "Ракетно-космическая техника",               "r"),
    ("ФН",  "Фундаментальные науки",                     "f"),
]

FAC_AREA_CODE = {
    "ИУ": "09", "ИБМ": "38", "МТ": "15", "СМ": "24",
    "ПИШ": "09", "БМТ": "12", "РЛ": "11", "Э": "13",
    "РК": "24", "ФН": "01",
}

# ── Кафедры (уникальные названия) ─────────────
FACULTY_DEPT_NAMES = {
    "ИУ": [
        "Теоретическая информатика и компьютерные технологии",
        "Прикладное программное обеспечение и системный анализ",
        "Компьютерные системы и сети",
        "Системы автоматического управления и интеллектуальные алгоритмы",
    ],
    "ИБМ": [
        "Промышленная логистика и управление цепями поставок",
        "Экономика и организация наукоёмкого производства",
        "Инновационное предпринимательство и технологический менеджмент",
        "Информационные технологии в бизнес-процессах",
    ],
    "МТ": [
        "Технология машиностроения и автоматизация производства",
        "Инструментальная техника и режущие инструменты",
        "Оборудование и технологии сварочного производства",
        "Материаловедение и поверхностное упрочнение деталей",
    ],
    "СМ": [
        "Специальные технологии высокоточного машиностроения",
        "Системы вооружения и комплексы специального назначения",
        "Гидравлические и пневматические системы спецтехники",
        "Прецизионная механика и регулировка приборов высокой точности",
    ],
    "ПИШ": [
        "Искусственный интеллект и машинное обучение в инженерии",
        "Цифровое производство и промышленный интернет вещей",
        "Инженерный анализ данных и цифровые двойники производств",
    ],
    "БМТ": [
        "Медицинские информационные технологии и телемедицина",
        "Биомедицинские приборы и инструментальные методы исследования",
        "Биотехнические системы и реабилитационная инженерия",
    ],
    "РЛ": [
        "Квантовая и оптическая электроника",
        "Антенны и сверхвысокочастотные радиоустройства",
        "Радиотехника и системы передачи информации",
        "Лазерные и оптоэлектронные системы и технологии",
    ],
    "Э": [
        "Паровые и газотурбинные установки и двигатели",
        "Холодильная и криогенная техника и технологии",
        "Гидравлические машины и гидропневмоавтоматика",
    ],
    "РК": [
        "Проектирование и испытание ракетных и космических комплексов",
        "Космические системы дистанционного зондирования Земли",
        "Жидкостные ракетные двигатели и энергетика летательных аппаратов",
        "Системы управления летательными и космическими аппаратами",
    ],
    "ФН": [
        "Математическое моделирование и вычислительные методы",
        "Теоретическая механика и теория машин и механизмов",
        "Физика конденсированных сред и нанотехнологии",
        "Химия и химическая технология новых конструкционных материалов",
    ],
}

SPECIALITIES = [
    "Прикладная информатика", "Информационная безопасность",
    "Программная инженерия", "Автоматизация технологических процессов",
    "Мехатроника и робототехника", "Биомедицинская инженерия",
    "Вычислительные машины, комплексы и системы",
    "Математика и компьютерные науки", "Управление в технических системах",
    "Инженерия данных", "Информационные системы и технологии",
    "Радиотехника", "Электроника и наноэлектроника", "Оптотехника",
    "Машиностроение", "Технология машиностроения",
    "Ракетные комплексы и космонавтика", "Двигатели летательных аппаратов",
]

SUBJECT_NAMES = [
    "Математический анализ", "Линейная алгебра", "Дискретная математика",
    "Теория вероятностей и математическая статистика",
    "Дифференциальные уравнения", "Программирование",
    "Структуры и алгоритмы данных", "Базы данных",
    "Операционные системы", "Компьютерные сети", "Архитектура ЭВМ",
    "Теория алгоритмов", "Машинное обучение", "Интеллектуальные системы",
    "Информационная безопасность", "Криптография",
    "Системное программирование", "Объектно-ориентированное программирование",
    "Веб-разработка", "Параллельные вычисления",
    "Цифровая обработка сигналов", "Теория управления",
    "Физика", "Химия", "История", "Иностранный язык",
    "Физическая культура", "Экономика",
    "Теоретическая механика", "Сопротивление материалов",
    "Электротехника", "Электроника", "Метрология",
    "Управление проектами", "Инженерная графика",
    "Безопасность жизнедеятельности", "Экология",
    "Численные методы", "Функциональный анализ",
    "Компьютерное зрение", "Обработка естественного языка",
    "Распределённые системы", "Облачные вычисления",
    "Тестирование программного обеспечения",
]

SUBJECT_TYPES  = ["основной", "факультатив", "общеобразовательный", "профессиональный"]
EXAM_TYPES     = ["Экзамен", "Зачёт", "Дифференцированный зачёт"]
PASSED_TYPES   = ["Досрочно", "В срок", "Досдача", "Комиссия"]
SCORE_TYPES    = ["РК", "ДЗ", "Лаб", "Экзамен", "Контрольная"]
LESSON_TYPES   = ["Лекция", "Лабораторная", "Семинар", "Практика", "Консультация"]
STATUS_WEIGHTS  = {"Обучается": 0.85, "Академический отпуск": 0.07, "Отчислен": 0.05, "Выпускник": 0.03}
FUNDING_WEIGHTS = {"Бюджет": 0.55, "Контракт": 0.40, "Целевое": 0.05}
CITIZENSHIPS = (["Россия"] * 85 + ["Беларусь"] * 5 + ["Казахстан"] * 5 +
                ["Китай", "Вьетнам", "Сирия", "Иран", "Индия",
                 "Египет", "Узбекистан", "Азербайджан", "Армения", "Молдова"])

MALE_NAMES = [
    "Александр","Дмитрий","Максим","Сергей","Андрей","Иван","Артём","Никита",
    "Михаил","Роман","Владимир","Егор","Павел","Кирилл","Илья","Глеб","Матвей",
    "Фёдор","Тимур","Руслан","Денис","Евгений","Алексей","Олег","Игорь",
    "Константин","Леонид","Виктор","Антон","Арсений","Марк","Станислав",
]
FEMALE_NAMES = [
    "Анна","Мария","Екатерина","Александра","Дарья","Полина","Алина","Виктория",
    "Елизавета","Ксения","Вероника","София","Татьяна","Ольга","Ирина","Надежда",
    "Юлия","Наталья","Людмила","Галина","Валерия","Карина","Диана","Светлана",
]
SURNAMES_M = [
    "Иванов","Петров","Сидоров","Кузнецов","Смирнов","Попов","Васильев",
    "Фёдоров","Морозов","Волков","Соколов","Лебедев","Козлов","Новиков",
    "Орлов","Макаров","Зайцев","Соловьёв","Борисов","Яковлев","Громов",
    "Семёнов","Степанов","Крылов","Воронов","Данилов","Тихонов","Белов",
    "Голубев","Михайлов","Королёв","Куликов","Савельев","Щербаков","Суворов",
    "Рябов","Журавлёв","Виноградов","Герасимов","Павлов","Захаров","Ершов",
    "Никитин","Комаров","Анисимов","Тарасов","Пономарёв","Мальцев","Прокофьев",
    "Кириллов","Антонов","Беляев","Чернов","Исаев","Федотов","Карпов","Власов",
]
PATRONYMICS_M = [
    "Александрович","Дмитриевич","Сергеевич","Андреевич","Иванович",
    "Максимович","Павлович","Романович","Владимирович","Егорович",
    "Николаевич","Михайлович","Алексеевич","Олегович","Игоревич",
    "Юрьевич","Константинович","Леонидович","Антонович","Арсеньевич",
    "Витальевич","Кириллович","Тимурович","Денисович","Евгеньевич",
    "Вячеславович","Анатольевич","Борисович","Геннадьевич","Валерьевич",
]
SURNAMES_F    = [s + "а" for s in SURNAMES_M]
PATRONYMICS_F = [p.replace("ович","овна").replace("евич","евна") for p in PATRONYMICS_M]

# ── Транслитерация кириллицы → латиница (1 символ) ──
_CYR = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'j','з':'z',
    'и':'i','й':'j','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r',
    'с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c','ч':'c','ш':'s','щ':'s',
    'ъ':'','ы':'y','ь':'','э':'e','ю':'u','я':'y',
}

def _lat1(word: str) -> str:
    return _CYR.get(word[0].lower(), word[0].lower()) if word else ''

# ── Helpers ───────────────────────────────────
def rdate(y1, y2):
    s = date(y1, 1, 1)
    return s + timedelta(days=random.randint(0, (date(y2, 12, 31) - s).days))

def rtime():
    return time(random.choice([8,9,10,11,12,13,14,15,16,17]), random.choice([0,30]))

def wchoice(d):
    return random.choices(list(d.keys()), weights=list(d.values()), k=1)[0]

def make_person():
    g = random.choice(["Мужской","Женский"])
    if g == "Мужской":
        return random.choice(MALE_NAMES), random.choice(SURNAMES_M), \
               (random.choice(PATRONYMICS_M) if random.random()>0.05 else None), g
    return random.choice(FEMALE_NAMES), random.choice(SURNAMES_F), \
           (random.choice(PATRONYMICS_F) if random.random()>0.05 else None), g

_nick_cnt: dict = defaultdict(int)

def make_nickname(surname, first_name, patronymic, enroll_year, fac_letter):
    """
    Формат: {s}{f}{p?}{YY}{fac_letter}{seq:04d}
    Пример: kfi23u0215, ya19f0003
    """
    prefix = _lat1(surname) + _lat1(first_name) + (_lat1(patronymic) if patronymic else '') \
             + str(enroll_year)[-2:] + fac_letter
    _nick_cnt[prefix] += 1
    return (prefix + f"{_nick_cnt[prefix]:04d}")[:10]

# ── Страницы ──────────────────────────────────
BASE_URL = "https://lks.bmstu.ru"

def gen_pages(n=200):
    tmpl = [
        ("/","home"),("/dashboard","home"),("/news","home"),("/search","home"),
        ("/help","home"),("/notifications","home"),("/faq","home"),
        ("/exams","exam"),("/exams/schedule","exam"),("/exams/results","exam"),
        ("/profile","profile"),("/profile/settings","profile"),
        ("/profile/grades","profile"),("/profile/photo","profile"),
        ("/profile/documents","profile"),
        ("/library","library"),("/library/search","library"),
        ("/schedule","schedule"),("/schedule/week","schedule"),
        ("/schedule/month","schedule"),("/schedule/exam","schedule"),
        ("/grades","grades"),("/grades/current","grades"),
        ("/grades/history","grades"),("/grades/report","grades"),
    ]
    for i in range(1, 60):
        tmpl.append((f"/courses/{i}", "course"))
        tmpl.append((f"/courses/{i}/materials", "course"))
    for i in range(1, 40):
        tmpl += [(f"/exams/{i}","exam")]
    for i in range(1, 30):
        tmpl += [(f"/library/book/{i}","library")]
    for i in range(1, 20):
        tmpl += [(f"/courses/{i}/tasks","course")]

    pages = []
    for pid, (path, sec) in enumerate(tmpl[:n], 1):
        slug = path.strip("/").split("/")[-1] or "Главная"
        pages.append((pid, BASE_URL + path, slug.capitalize(), sec))
    return pages

# ─────────────────────────────────────────────
# GENERATE
# ─────────────────────────────────────────────

def generate():
    degrees    = [(i+1, n) for i,n in enumerate(DEGREE_NAMES)]
    forms      = [(i+1, n) for i,n in enumerate(FORM_NAMES)]
    deg_id_map = {n: i+1 for i,n in enumerate(DEGREE_NAMES)}

    faculties  = [(i+1, code, name, letter) for i,(code,name,letter) in enumerate(FACULTY_DATA)]

    # Кафедры
    depts_int = []   # (dept_id, fac_id, dept_name, fac_code, fac_letter, dept_num_in_fac)
    for fac_id, fac_code, _, fac_letter in faculties:
        for j, dname in enumerate(FACULTY_DEPT_NAMES[fac_code]):
            depts_int.append((len(depts_int)+1, fac_id, dname, fac_code, fac_letter, j+1))

    departments_db = [(d[0], d[1], d[2]) for d in depts_int]

    # Программы
    edu_cnt = defaultdict(int)
    progs_int = []  # (pid, deg_id, form_id, dept_id, edu_code, yos, profile, spec,
                    #  deg_name, fac_code, fac_letter, dept_num)
    for dept_id, fac_id, dname, fac_code, fac_letter, dept_num in depts_int:
        for _ in range(random.randint(2, 3)):
            pid      = len(progs_int) + 1
            dname_   = random.choice(DEGREE_NAMES)
            area     = FAC_AREA_CODE[fac_code]
            level    = DEGREE_AREA[dname_]
            key      = (area, level)
            edu_cnt[key] += 1
            edu_code = f"{area}.{level}.{edu_cnt[key]:02d}"  # 01.03.02 format
            yos      = DEGREE_YEARS[dname_]
            profile  = f"Профиль {random.randint(1,9)}" if random.random() > 0.3 else None
            spec     = random.choice(SPECIALITIES)
            progs_int.append((pid, deg_id_map[dname_], random.choice(forms)[0], dept_id,
                              edu_code, yos, profile, spec,
                              dname_, fac_code, fac_letter, dept_num))

    programs_db = [p[:8] for p in progs_int]

    # Группы: когортный подход.
    # Когорта = (pid, enroll_year, grp_seq). Для каждой когорты создаём
    # запись study_group на каждый пройденный семестр (1..current_sem).
    # Имя группы: {FAC_CODE}{dept_num}-{sem}{grp_seq}{SUFFIX}
    # Студент связывается со ВСЕМИ группами своей когорты (все прошедшие семестры).
    study_groups = []
    # cohort_sems[(pid, enroll_year, grp_seq)] = {sem: group_id}
    cohort_sems: dict = {}
    # prog_to_cohorts[pid] = [(enroll_year, grp_seq), ...]
    prog_to_cohorts: dict = defaultdict(list)

    for p in progs_int:
        pid, _, _, _, _, _, _, _, deg_name, fac_code, fac_letter, dept_num = p
        max_sem    = DEGREE_MAX_SEM[deg_name]
        suffix     = DEGREE_SUFFIX[deg_name]
        max_course = max_sem // 2
        valid_yrs  = [y for y in range(2019, 2025)
                      if 1 <= (2024 - y + 1) <= max_course]
        if not valid_yrs:
            valid_yrs = [2024]

        # Для каждого учебного года набора создаём 2-4 параллельные группы
        for enroll_year in random.sample(valid_yrs, min(len(valid_yrs), random.randint(1, 3))):
            course      = 2024 - enroll_year + 1
            current_sem = min(course * 2, max_sem)
            n_grps      = random.randint(2, 4)

            for grp_seq in range(1, n_grps + 1):
                cohort_key = (pid, enroll_year, grp_seq)
                cohort_sems[cohort_key] = {}
                prog_to_cohorts[pid].append((enroll_year, grp_seq))

                # Одна запись study_group на каждый семестр когорты
                for sem in range(1, current_sem + 1):
                    gid        = len(study_groups) + 1
                    course_sem = (sem + 1) // 2
                    gname      = f"{fac_code}{dept_num}-{sem}{grp_seq}{suffix}"
                    study_groups.append((gid, pid, gname, enroll_year, course_sem, sem))
                    cohort_sems[cohort_key][sem] = gid

    # Предметы
    used_subj: set = set()
    subjects = []
    all_dept_names = [d[2] for d in depts_int]
    for _ in range(min(len(SUBJECT_NAMES) * 2, 350)):
        name = random.choice(SUBJECT_NAMES)
        sem  = random.randint(1, 8)
        if (name, sem) in used_subj:
            continue
        used_subj.add((name, sem))
        sid = len(subjects) + 1
        subjects.append((
            sid, name, sem, random.randint(2, 6) * 16,
            random.choice(all_dept_names),
            random.choice(SUBJECT_TYPES),
            random.randint(4, 12) if random.random() > 0.5 else None,
            random.randint(2, 4), random.randint(3, 8),
        ))

    prog_subjects = {p[0]: random.sample([s[0] for s in subjects],
                    min(random.randint(*SUBJECTS_PER_PROG), len(subjects)))
                    for p in progs_int}

    # Экзамены
    exams = []
    subj_exams = defaultdict(list)
    for s in subjects:
        for _ in range(random.randint(1, 2)):
            eid = len(exams) + 1
            exams.append((eid, s[0], rdate(2024,2025), rtime(),
                          random.choice(EXAM_TYPES), random.choice(PASSED_TYPES)))
            subj_exams[s[0]].append(eid)

    pages = gen_pages(200)

    # Пользователи
    users = []
    usg   = []
    usub  = []
    uexam = []
    scores = []
    attend = []
    seen_usub  = set()
    seen_uexam = set()

    for uid in range(1, N_USERS + 1):
        first, sure, patr, gender = make_person()
        prog      = random.choice(progs_int)
        pid       = prog[0]
        fac_code  = prog[9]
        fac_ltr   = prog[10]

        grps      = prog_to_grps.get(pid, [])
        grp_id    = random.choice(grps) if grps else 1
        enroll_yr = random.choice([2021, 2022, 2023, 2024])
        course    = 2024 - enroll_yr + 1

        nick = make_nickname(sure, first, patr, enroll_yr, fac_ltr)
        users.append((uid, nick, first, sure, patr,
                      rdate(1998, 2006), gender, random.choice(CITIZENSHIPS),
                      enroll_yr, wchoice(FUNDING_WEIGHTS),
                      random.random() < 0.3, wchoice(STATUS_WEIGHTS), course))
        usg.append((uid, grp_id))

        sids    = prog_subjects.get(pid, [])
        chosen  = random.sample(sids, min(random.randint(4, max(4, len(sids))), len(sids)))
        ability = float(np.clip(np.random.normal(0.70, 0.15), 0.25, 0.99))

        for sid in chosen:
            if (uid, sid) not in seen_usub:
                seen_usub.add((uid, sid))
                usub.append((uid, sid))

            for eid in subj_exams.get(sid, []):
                if (uid, eid) not in seen_uexam:
                    seen_uexam.add((uid, eid))
                    uexam.append((uid, eid))

            for attempt in range(1, random.randint(*SCORES_PER_SUBJECT) + 1):
                max_sc = random.choice([10, 20, 25, 50, 100])
                sc     = int(np.clip(ability * max_sc + np.random.normal(0, max_sc * 0.08),
                                     0, max_sc))
                module = random.randint(1, 3)
                scores.append((len(scores)+1, sid, uid, rdate(2024,2025),
                               random.choice(SCORE_TYPES), sc, max_sc,
                               attempt, sc >= max_sc * 0.6, module))

            atten_p = 0.4 + ability * 0.5
            for _ in range(random.randint(*LESSONS_PER_SUBJECT)):
                attend.append((len(attend)+1, sid, uid, rdate(2024,2025),
                               rtime(), random.choice(LESSON_TYPES),
                               random.random() < atten_p))

    return dict(
        degrees=degrees, forms=forms,
        faculties=[(f[0], f[2]) for f in faculties],
        departments=departments_db, programs=programs_db,
        study_groups=study_groups, subjects=subjects, exams=exams,
        pages=pages, users=users,
        user_study_group=usg, user_subject=usub,
        user_exam=uexam, scores=scores, attendance=attend,
    )

# ─────────────────────────────────────────────
# INSERT
# ─────────────────────────────────────────────

def insert_pg(data):
    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    cur  = conn.cursor()

    def bulk(sql, rows, chunk=5000):
        if not rows:
            return
        for i in range(0, len(rows), chunk):
            execute_values(cur, sql, rows[i:i+chunk])
        conn.commit()

    print("Очищаем edu …")
    cur.execute("""
        TRUNCATE edu.attendance, edu.score, edu.user_exam,
            edu.user_subject, edu.user_study_group, edu.exam,
            edu.subject, edu."user", edu.study_group, edu.program,
            edu.department, edu.faculty, edu.education_form,
            edu.education_degree, edu.page
        RESTART IDENTITY CASCADE;
    """)
    conn.commit()

    bulk("INSERT INTO edu.education_degree (degree_id,degree_name) VALUES %s",
         data["degrees"])
    bulk("INSERT INTO edu.education_form   (form_id,form_name)     VALUES %s",
         data["forms"])
    print(f"faculty           {len(data['faculties'])}")
    bulk("INSERT INTO edu.faculty (faculty_id,faculty_name) VALUES %s",
         data["faculties"])
    print(f"department        {len(data['departments'])}")
    bulk("INSERT INTO edu.department (department_id,faculty_id,department_name) VALUES %s",
         data["departments"])
    print(f"program           {len(data['programs'])}")
    bulk("""INSERT INTO edu.program
             (program_id,degree_id,form_id,department_id,
              education_code,year_of_study,profile,speciality) VALUES %s""",
         data["programs"])
    print(f"study_group       {len(data['study_groups'])}")
    bulk("""INSERT INTO edu.study_group
             (group_id,program_id,group_name,enrollment_year,course,semestr) VALUES %s""",
         data["study_groups"])
    print(f"subject           {len(data['subjects'])}")
    bulk("""INSERT INTO edu.subject
             (subject_id,subject_name,semestr,credit_hours,
              department,type,count_labs,count_rk,count_dz) VALUES %s""",
         data["subjects"])
    print(f"exam              {len(data['exams'])}")
    bulk("""INSERT INTO edu.exam
             (exam_id,subject_id,exam_date,exam_time,exam_type,passed_type) VALUES %s""",
         data["exams"])
    print(f"page              {len(data['pages'])}")
    bulk("INSERT INTO edu.page (page_id,page_path,page_name,page_section) VALUES %s",
         data["pages"])
    print(f"user              {len(data['users'])}")
    bulk("""INSERT INTO edu."user"
             (user_id,user_nickname,first_name,surname,middle_name,
              birth_date,gender,citizenship,enrollment_year,
              funding_type,dormitory_resident,status,current_course) VALUES %s""",
         data["users"])
    print(f"user_study_group  {len(data['user_study_group'])}")
    bulk("INSERT INTO edu.user_study_group (user_id,group_id) VALUES %s",
         data["user_study_group"])
    print(f"user_subject      {len(data['user_subject'])}")
    bulk("INSERT INTO edu.user_subject (user_id,subject_id) VALUES %s",
         data["user_subject"])
    print(f"user_exam         {len(data['user_exam'])}")
    bulk("INSERT INTO edu.user_exam (user_id,exam_id) VALUES %s",
         data["user_exam"])
    print(f"score             {len(data['scores'])}")
    bulk("""INSERT INTO edu.score
             (score_id,subject_id,user_id,score_date,score_type,
              score,max_score,attempt_number,is_passed,module) VALUES %s""",
         data["scores"])
    print(f"attendance        {len(data['attendance'])}")
    bulk("""INSERT INTO edu.attendance
             (attendance_id,subject_id,user_id,
              lesson_date,lesson_time,lesson_type,is_present) VALUES %s""",
         data["attendance"])

    cur.close()
    conn.close()
    print("\n✓ PostgreSQL заполнен.")

if __name__ == "__main__":
    print(f"Генерируем (N_USERS={N_USERS}) …")
    data = generate()
    for k in ("users","study_groups","subjects","exams","scores","attendance"):
        print(f"  {k:<20} {len(data[k]):>10,}")
    print("\nВставляем …")
    insert_pg(data)
