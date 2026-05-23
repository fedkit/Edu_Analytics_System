# Описание сущностей базы данных

---

## USER — Пользователь системы

Хранит информацию о студентах.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `UserID` | INT | NOT NULL | PK | Суррогатный первичный ключ пользователя |
| `UserNickname` | VARCHAR(10) | NOT NULL | AK 1.1 | Уникальный логин пользователя |
| `FirstName` | VARCHAR(100) | NOT NULL | — | Имя |
| `Surname` | VARCHAR(100) | NOT NULL | — | Фамилия |
| `MiddleName` | VARCHAR(100) | NULL | — | Отчество; NULL если отсутствует |
| `BirthDate` | DATE | NOT NULL | — | Дата рождения |
| `Gender` | VARCHAR(10) | NOT NULL | — | Пол |
| `Citizenship` | VARCHAR(100) | NOT NULL | — | Гражданство |
| `EnrollmentYear` | INT | NOT NULL | — | Год поступления |
| `FundingType` | VARCHAR(50) | NOT NULL | — | Тип финансирования |
| `DormitoryResident` | BOOLEAN | NOT NULL | — | Признак проживания в общежитии |
| `Status` | VARCHAR(50) | NOT NULL | — | Статус студента (обучается, отчислен, академический отпуск) |
| `CurrentCourse` | INT | NOT NULL | — | Текущий курс |

---

## SESSION — Сессия пользователя

Фиксирует отдельный визит пользователя на платформу.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `SessionID` | INT | NOT NULL | PK | Суррогатный первичный ключ сессии |
| `UserID` | INT | NOT NULL | FK → USER | Пользователь, которому принадлежит сессия |
| `SessionStart` | TIMESTAMP | NOT NULL | — | Дата и время начала сессии |
| `SessionEnd` | TIMESTAMP | NULL | — | Дата и время окончания; NULL если сессия активна |
| `DeviceType` | VARCHAR(50) | NOT NULL | — | Тип устройства |

---

## EVENT — Событие в сессии

Действие пользователя внутри сессии.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `EventID` | INT | NOT NULL | PK | Суррогатный первичный ключ события |
| `PageID` | INT | NOT NULL | FK → PAGE | Страница, на которой произошло событие |
| `NextPageID` | INT | NULL | FK → PAGE | Следующая страница перехода |
| `SessionID` | INT | NOT NULL | FK → SESSION, AK 1.1 | Сессия, в рамках которой произошло событие |
| `EventTime` | TIMESTAMP | NOT NULL | AK 1.2 | Время события; вместе с SessionID образует альтернативный ключ |
| `EventType` | VARCHAR(50) | NOT NULL | — | Тип действия пользователя |
| `ElementName` | VARCHAR(100) | NULL | — | Название элемента интерфейса |
| `Purpose` | VARCHAR(100) | NULL | — | Цель или контекст события |

---

## PAGE — Страница сайта

Справочник страниц платформы.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `PageID` | INT | NOT NULL | PK | Суррогатный первичный ключ страницы |
| `PagePath` | VARCHAR(255) | NOT NULL | AK 1.1 | Уникальный URL страницы |
| `PageName` | VARCHAR(255) | NOT NULL | — | Название страницы |
| `PageSection` | VARCHAR(100) | NOT NULL | — | Раздел сайта |

---

## STUDY_GROUP — Учебная группа

Объединяет студентов одного набора в рамках образовательной программы.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `GroupID` | INT | NOT NULL | PK | Суррогатный первичный ключ группы |
| `ProgramID` | INT | NOT NULL | FK → PROGRAM | Образовательная программа |
| `GroupName` | VARCHAR(50) | NOT NULL | AK 1.1 | Название группы |
| `EnrollmentYear` | INT | NOT NULL | AK 1.2 | Год поступления группы |
| `Course` | INT | NULL | — | Текущий курс обучения; NULL если группа выпустилась |
| `Semestr` | INT | NOT NULL | — | Текущий семестр; NULL если группа выпустилась |

---

## PROGRAM — Образовательная программа

Образовательные программы.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `ProgramID` | INT | NOT NULL | PK | Суррогатный первичный ключ программы |
| `DegreeID` | INT | NOT NULL | FK → EDUCATION_DEGREE | Уровень образования |
| `FormID` | INT | NOT NULL | FK → EDUCATION_FORM | Форма обучения |
| `DepartmentID` | INT | NOT NULL | FK → DEPARTMENT | Кафедра |
| `EducationCode` | VARCHAR(50) | NOT NULL | — | Код образовательной программы |
| `YearOfStudy` | INT | NOT NULL | — | Нормативный срок обучения |
| `Profile` | VARCHAR(100) | NULL | — | Профиль подготовки |
| `Speciality` | VARCHAR(100) | NOT NULL | — | Название специальности |

---

## EDUCATION_DEGREE — Уровень образования

Уровень образования.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `DegreeID` | INT | NOT NULL | PK | Суррогатный первичный ключ уровня |
| `DegreeName` | VARCHAR(100) | NOT NULL | — | Название уровня образования |

---

## EDUCATION_FORM — Форма обучения

Форма обучения.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `FormID` | INT | NOT NULL | PK | Суррогатный первичный ключ формы |
| `FormName` | VARCHAR(100) | NOT NULL | — | Название формы обучения |

---

## FACULTY — Факультет

Факультеты.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `FacultyID` | INT | NOT NULL | PK | Суррогатный первичный ключ факультета |
| `FacultyName` | VARCHAR(100) | NOT NULL | — | Название факультета |

---

## DEPARTMENT — Кафедра

Кафедры.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `DepartmentID` | INT | NOT NULL | PK | Суррогатный первичный ключ кафедры |
| `FacultyID` | INT | NOT NULL | FK → FACULTY | Факультет |
| `DepartmentName` | VARCHAR(100) | NOT NULL | — | Название кафедры |

---

## SUBJECT — Учебный предмет

Дисциплины.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `SubjectID` | INT | NOT NULL | PK | Суррогатный первичный ключ предмета |
| `SubjectName` | VARCHAR(200) | NOT NULL | — | Название дисциплины |
| `Semestr` | INT | NOT NULL | — | Семестр преподавания |
| `CreditHours` | INT | NOT NULL | — | Количество академических часов |
| `Department` | VARCHAR(100) | NOT NULL | — | Кафедра |
| `Type` | VARCHAR(50) | NOT NULL | — | Тип дисциплины |
| `CountLabs` | INT | NULL | — | Количество лабораторных работ |
| `CountRK` | INT | NULL | — | Количество рубежных контролей |
| `CountDZ` | INT | NULL | — | Количество домашних заданий |

---

## EXAM — Экзамен

Фиксирует экзаменационное мероприятие по предмету.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `ExamID` | INT | NOT NULL | PK | Суррогатный первичный ключ экзамена |
| `SubjectID` | INT | NOT NULL | FK → SUBJECT, AK 1.1 | Предмет экзамена |
| `ExamDate` | DATE | NOT NULL | AK 1.2 | Дата проведения экзамена |
| `ExamTime` | TIME | NOT NULL | AK 1.3 | Время начала экзамена |
| `ExamType` | VARCHAR(50) | NOT NULL | — | Тип экзамена |
| `PassedType` | VARCHAR(50) | NOT NULL | — | Тип попытки сдачи экзамена(досрочно, в срок, досдача, комиссия) |

---

## ATTENDANCE — Посещаемость

Фиксирует факт присутствия студента на конкретном занятии.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `AttendanceID` | INT | NOT NULL | PK | Суррогатный первичный ключ записи посещаемости |
| `SubjectID` | INT | NOT NULL | FK → SUBJECT | Предмет занятия |
| `UserID` | INT | NOT NULL | FK → USER | Студент |
| `LessonDate` | DATE | NOT NULL | — | Дата занятия |
| `LessonTime` | TIME | NOT NULL | — | Время занятия |
| `LessonType` | VARCHAR(50) | NOT NULL | — | Тип занятия (лекция, лабораторная и т.п.) |
| `IsPresent` | BOOLEAN | NOT NULL | — | Признак присутствия студента |

---

## SCORE — Оценки студента

Хранит детализированные оценки студента по дисциплине с указанием даты и попытки.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `ScoreID` | INT | NOT NULL | PK | Суррогатный первичный ключ оценки |
| `SubjectID` | INT | NOT NULL | FK → SUBJECT | Предмет |
| `UserID` | INT | NOT NULL | FK → USER | Студент |
| `ScoreDate` | DATE | NOT NULL | — | Дата выставления оценки |
| `ScoreType` | VARCHAR(50) | NOT NULL | — | Тип оценки (РК, ДЗ, лаб. и т.п.) |
| `Score` | INT | NOT NULL | — | Полученный балл |
| `MaxScore` | INT | NOT NULL | — | Максимально возможный балл |
| `AttemptNumber` | INT | NOT NULL | — | Номер попытки |
| `IsPassed` | BOOLEAN | NOT NULL | — | Признак успешной сдачи |
| `Module` | INT | NULL | — | Модуль  |

---

## USER_STUDY_GROUP — Связь студентов и групп

Ассоциативная сущность между USER и STUDY_GROUP.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `UserID` | INT | NOT NULL | PK, FK → USER | Студент |
| `GroupID` | INT | NOT NULL | PK, FK → STUDY_GROUP | Учебная группа |

---

## USER_SUBJECT — Связь студентов и предметов

Ассоциативная сущность между USER и SUBJECT.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `UserID` | INT | NOT NULL | PK, FK → USER | Студент |
| `SubjectID` | INT | NOT NULL | PK, FK → SUBJECT | Предмет |

---

## USER_EXAM — Связь студентов и экзаменов

Ассоциативная сущность между USER и EXAM.

| Атрибут | Тип | NULL | Ключ | Описание |
|---|---|---|---|---|
| `UserID` | INT | NOT NULL | PK, FK → USER | Студент |
| `ExamID` | INT | NOT NULL | PK, FK → EXAM | Экзамен |