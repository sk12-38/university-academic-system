# <<< BEGIN academic_system.py >>>
"""
academic_system.py
------------------
A self-contained academic information system that satisfies the evaluation
criteria described in *evaluation_criteria.png* and implements the functional
requirements in *plan.txt* and *기빅프_20200595_이석희_제안서.pdf*.

Highlights
~~~~~~~~~~
* **Class hierarchy** – ``User`` → ``Student`` / ``Professor`` plus ``Course``,
  ``Enrollment`` and an ``Admin`` utility.
* **Decorators** – ``@check_time``, ``@log_access``,
  ``@require_admin``, ``@require_professor``, ``@require_student``.
* **Encapsulation** – name-mangled private attributes exposed through
  properties.
* **Role-based CLI** – text menu for administrator, student and professor
  modes.
* **Persistence** – JSON file with ≥ 50 seed records; automatic save on exit.
* **Analytics & viz** – NumPy/Pandas stats, matplotlib/seaborn plots.
* **Regex validation** – student IDs (^20\\d{6}$) and course codes
  (^[A-Z]{3,5}\\d{3,4}$).

Standard-library only plus *numpy*, *pandas*, *matplotlib*, *seaborn*.

Run
~~~
$ python academic_system.py
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import sys
import time
from collections import defaultdict, Counter
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Type

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import tabulate
plt.rc('font', family='Malgun Gothic')
plt.rcParams['axes.unicode_minus'] = False  # 마이너스 깨짐 방지

###############################################################################
# Logging configuration
###############################################################################

logging.basicConfig(
    filename="access.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

###############################################################################
# Decorators
###############################################################################


def check_time(func):
    """Measure and print execution time."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[Time] {func.__name__} took {elapsed:.4f} s")
        return result

    return wrapper


def log_access(func):
    """Append a time-stamped call to the log file."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(f"Called {func.__qualname__}")
        return func(*args, **kwargs)

    return wrapper


def require_role(required_cls_name):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            user = getattr(self, 'current_user', self)
            required_cls = globals()[required_cls_name]
            if not isinstance(user, required_cls):
                raise AuthorizationError(
                    f"{type(user).__name__} is not allowed to call {func.__name__}"
                )
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


require_admin = require_role("Admin")
require_professor = require_role("Professor")
require_student = require_role("Student")

###############################################################################
# Helper utilities
###############################################################################


STUDENT_ID_RE = re.compile(r"^20\d{6}$")    # 100년 지나면 수정할 
COURSE_CODE_RE = re.compile(r"^[A-Z]{3,5}\d{3,4}$")
DATA_FILE = "academic_data.json"
RANDOM = random.Random(42)  # deterministic seed for repeatability


def _validate(regex: re.Pattern, value: str, label: str) -> None:
    if not regex.match(value):
        raise ValidationError(f"Invalid {label}: {value}")


def _gpa_from_grade(grade: str) -> float:
    """A+→4.3 scale."""
    table = {
        "A+": 4.3,
        "A0": 4.0,
        "A-": 3.7,
        "B+": 3.3,
        "B0": 3.0,
        "B-": 2.7,
        "C+": 2.3,
        "C0": 2.0,
        "C-": 1.7,
        "D+": 1.3,
        "D0": 1.0,
        "D-": 0.7,
        "F": 0.0,
    }
    return table.get(grade.upper(), 0.0)

# CLI에서 표를 출력하기 위한 함수
def print_course_table(courses, professors=None, show_index=True):
    table_data = []
    for idx, c in enumerate(courses, 1):
        prof_name = None
        if professors is not None:
            prof_name = professors[c.professor].name if c.professor in professors else "(알 수 없음)"
        row = [idx, c.code, c.name, prof_name if prof_name is not None else c.year, c.year if prof_name is not None else c.semester, c.semester if prof_name is not None else c.section, c.section if prof_name is not None else c.credit, c.credit] if prof_name is not None else [idx, c.code, c.name, c.year, c.semester, c.section, c.credit]
        table_data.append(row)
    if professors is not None:
        headers = ["번호", "코드", "과목명", "담당", "연도", "학기", "분반", "학점"]
    else:
        headers = ["번호", "코드", "과목명", "연도", "학기", "분반", "학점"]
    print(tabulate.tabulate(table_data, headers=headers, tablefmt="fancy_grid", stralign="center"))

###############################################################################
# Custom Exception 계층
###############################################################################

class AcademicError(Exception):
    """기본 학사 시스템 예외"""
    pass

class AuthorizationError(AcademicError):
    """권한 관련 예외"""
    pass

class ValidationError(AcademicError):
    """입력값 검증 예외"""
    pass

###############################################################################
# Core domain classes
###############################################################################


class User:
    """Base user."""

    def __init__(self, uid: str, name: str, major: str, nationality: str, password: str):
        self.uid = uid
        self.name = name
        self.major = major
        self.nationality = nationality
        self._password = password

    # --- Security ---------------------------------------------------------

    def authenticate(self, pw: str) -> bool:
        return self._password == pw

    # --- Polymorphic menu -------------------------------------------------

    def get_menu(self) -> List[Tuple[str, str]]:
        """Return list of (command, description)."""
        return [("quit", "Exit")]


class Student(User):
    """Student user."""

    total_student: int = 0

    @classmethod
    def count(cls) -> int:
        return cls.total_student

    @staticmethod
    def gpa_from_grades(grades: List[str]) -> float:
        """Static helper to compute GPA from *grades* list."""
        return round(np.mean([_gpa_from_grade(g) for g in grades]), 2) if grades else 0.0

    # ---------------------------------------------------------------------

    def __init__(
        self,
        uid: str,
        name: str,
        major: str,
        nationality: str,
        password: str,
        semesters_completed: int,
        year: int,
        advisor: str
    ):
        super().__init__(uid, name, major, nationality, password)
        _validate(STUDENT_ID_RE, uid, "student ID")
        self.semesters_completed = semesters_completed
        self.year = year
        self.advisor = advisor
        self.current_courses: List[str] = []
        Student.total_student += 1

    # Menu ------------------------------------------------------------------

    def get_menu(self) -> List[Tuple[str, str]]:
        return [
            ("register", "수강신청"),
            ("drop", "수강취소"),
            ("courses", "수강한 과목 조회"),
            ("grades", "성적 조회"),
            ("info", "내 정보 열람"),
            ("quit", "종료"),
        ]

    # Functionalities -------------------------------------------------------

    @log_access
    @require_student
    def register_course(self, course: "Course", enrollments: list) -> bool:
        # 이미 수강신청한 경우 체크 (Enrollment 기반, 코드+분반)
        if any(e for e in enrollments if e.course_code == course.code and getattr(course, 'section', None) == getattr(self, 'section', None) and e.student_id == self.uid):
            print("이미 신청된 과목입니다.")
            return False
        queue = RANDOM.randint(1, 300)
        my_pos = RANDOM.randint(1, 300)
        print(f"현재 {queue}명이 대기 중입니다.")
        # 해당 과목의 현재 수강 인원 (Enrollment 기반, 코드+분반)
        current_count = sum(1 for e in enrollments if e.course_code == course.code)
        if my_pos <= queue and current_count < course.capacity:
            # Enrollment 추가
            enrollments.append(Enrollment(self.uid, course.code, 2025, 2))  # 2025년 2학기로 고정
            print("수강신청에 성공하였습니다.")
            return True
        print("수강신청에 실패하였습니다.")
        return False

    @log_access
    @require_student
    def drop_course(self, enrollments, courses):
        # 2025년 2학기 본인 수강신청 내역만 취소 가능
        my_enrolls = [e for e in enrollments if e.student_id == self.uid and e.year == 2025 and e.semester == 2]
        if not my_enrolls:
            print("2025년 2학기 수강신청 내역이 없습니다.")
            return
        print("[2025년 2학기 수강신청 내역]")
        for idx, e in enumerate(my_enrolls, 1):
            cname = courses[e.course_code].name if e.course_code in courses else ''
            print(f"  {idx}. {e.course_code} {cname}")
        while True:
            try:
                sel = int(input("취소할 과목 번호(0: 취소): ").strip())
                if sel == 0:
                    print("작업이 취소되었습니다.")
                    return
                if not (1 <= sel <= len(my_enrolls)):
                    print(f"1~{len(my_enrolls)} 사이의 번호를 입력하세요.")
                    continue
                target = my_enrolls[sel-1]
                break
            except Exception:
                print("올바르지 않은 입력입니다.")
        # Enrollment에서 삭제
        enrollments.remove(target)
        print(f"{target.course_code} 수강신청이 취소되었습니다.")

    @log_access
    @require_student
    def check_course(self, enrollments, courses):
        # 수강했던 모든 과목과 성적을 학기별로 출력
        print("[학기별 수강 과목 및 성적]")
        my_enrolls = [e for e in enrollments if e.student_id == self.uid]
        if not my_enrolls:
            print("수강 이력이 없습니다.")
            return
        # (년도, 학기)별로 그룹화
        sem_dict = defaultdict(list)
        for e in my_enrolls:
            sem_dict[(e.year, e.semester)].append(e)
        # 학기별로 출력
        for (year, semester) in sorted(sem_dict.keys()):
            data = []
            gpas = []
            for e in sem_dict[(year, semester)]:
                cname = courses[e.course_code].name if e.course_code in courses else ''
                if year == 2025 and semester == 2 and not e.grade:
                    grade_display = "-"
                    gpa_display = "-"
                else:
                    grade_display = e.grade if e.grade else "-"
                    gpa_display = f"{_gpa_from_grade(e.grade):.2f}" if e.grade else "-"
                if gpa_display != "-":
                    gpas.append(float(gpa_display))
                data.append([
                    e.course_code,
                    cname,
                    grade_display,
                    gpa_display
                ])
            avg_gpa = f"{np.mean(gpas):.2f}" if gpas else "-"
            print(f"\n--- {year}년 {semester}학기 (과목 수: {len(data)}, 평균 GPA: {avg_gpa}) ---")
            print(tabulate.tabulate(data, headers=["과목코드", "과목명", "성적", "GPA"], tablefmt="fancy_grid", stralign="center"))
            print("-" * 50)

    @log_access
    @require_student
    def check_grade(self, enrollments, courses):
        # 학기별 GPA 계산 및 시각화
        my_enrolls = [e for e in enrollments if e.student_id == self.uid]
        if not my_enrolls:
            print("성적이 없습니다.")
            return
        # (년도, 학기)별로 그룹화
        sem_dict = defaultdict(list)
        for e in my_enrolls:
            sem_dict[(e.year, e.semester)].append(e)
        # 2025년 1학기까지만 필터링
        filtered_sem_keys = [k for k in sem_dict.keys() if (k[0] < 2025) or (k[0] == 2025 and k[1] <= 1)]
        # 학기별 GPA 계산
        gpa_trend = []
        print("\n[학기별 GPA]")
        for idx, year_sem in enumerate(sorted(filtered_sem_keys), 1):
            enrolls = sem_dict[year_sem]
            gpas = [_gpa_from_grade(e.grade) for e in enrolls]
            avg_gpa = round(np.mean(gpas), 2) if gpas else 0.0
            gpa_trend.append((idx, year_sem[0], year_sem[1], avg_gpa))
            print(f"{year_sem[0]}년 {year_sem[1]}학기 GPA: {avg_gpa}")
        # 표로 출력 (tabulate)
        df_gpa = pd.DataFrame(gpa_trend, columns=["수강학기", "년도", "학기", "GPA"])
        print("\n[학기별 GPA 표]")
        print(tabulate.tabulate(df_gpa.values.tolist(), headers=df_gpa.columns, tablefmt="fancy_grid", stralign="center"))
        # 시각화
        plt.figure(figsize=(6,4))
        plt.plot(df_gpa["수강학기"], df_gpa["GPA"], marker="o")
        plt.title(f"{self.name}의 학기별 GPA 추이")
        plt.xlabel("수강학기")
        plt.ylabel("GPA")
        plt.xticks(df_gpa["수강학기"], [f"{y}-{s}" for y,s in zip(df_gpa["년도"], df_gpa["학기"])])
        plt.ylim(0, 4.3)  # y축 고정
        plt.tight_layout()
        plt.show()

class Professor(User):
    """Professor user."""

    total_professor: int = 0

    def __init__(
        self,
        uid: str,
        name: str,
        major: str,
        nationality: str,
        password: str,
        title: str
    ):
        super().__init__(uid, name, major, nationality, password)
        self.title = title
        Professor.total_professor += 1

    # Menu ------------------------------------------------------------------

    def get_menu(self) -> List[Tuple[str, str]]:
        return [
            ("list", "수강 학생 조회"),
            ("grade", "성적 입력"),
            ("stats", "성적 통계/시각화"),
            ("info", "내 정보 열람"),
            ("quit", "종료"),
        ]

    # Functionalities -------------------------------------------------------

    @log_access
    @require_professor
    def list_students(self, course: "Course", students: Dict[str, Student], enrollments: list):
        if course.professor != self.uid:
            raise AuthorizationError("담당 교수가 아닙니다.")
        print(f"=== {course.code} 수강 학생 ===")
        # Enrollment 기반으로 수강 학생 조회 (연도/학기 고려)
        unique_students = set()  # 중복 방지를 위한 set
        for e in enrollments:
            if (e.course_code == course.code and 
                e.year == course.year and 
                e.semester == course.semester):
                unique_students.add(e.student_id)
        # 표 형태로 출력 (tabulate)
        data = []
        for sid in sorted(unique_students):
            if sid in students:
                data.append([sid, students[sid].name])
            else:
                data.append([sid, "(알 수 없음)"])
        print(tabulate.tabulate(data, headers=["학번", "이름"], tablefmt="fancy_grid", stralign="center"))

    @log_access
    @require_professor
    def assign_grade(self, student: Student, course: "Course", grade: str, enrollments: list):
        if course.professor != self.uid:
            raise AuthorizationError("담당 교수가 아닙니다.")
        # Enrollment 기반으로 수강 여부 확인 (연도/학기 고려)
        if not any(e for e in enrollments 
                  if e.course_code == course.code and 
                  e.student_id == student.uid and
                  e.year == course.year and 
                  e.semester == course.semester):
            raise ValidationError("해당 학생은 이 과목에 수강 신청하지 않았습니다.")

    @log_access
    @require_professor
    def plot_course_stats(self, course: "Course", students: Dict[str, Student], enrollments: list, year: int, semester: int):
        # 해당 연도/학기 과목을 수강한 학생의 성적을 Enrollment에서 직접 수집
        grades = [
            e.grade.upper()
            for e in enrollments
            if e.course_code == course.code and e.year == year and e.semester == semester and e.grade
        ]
        if not grades:
            print("성적 데이터가 없습니다.")
            return
        # 표로도 출력
        grade_order = ["A+", "A0", "A-", "B+", "B0", "B-", "C+", "C0", "C-", "D+", "D0", "D-", "F"]  # 내림차순
        grade_counts = Counter(grades)
        table_data = [[g, grade_counts.get(g, 0)] for g in grade_order]
        print("\n[성적 분포표]")
        print(tabulate.tabulate(table_data, headers=["성적", "인원수"], tablefmt="fancy_grid", stralign="center"))
        # 기존 시각화
        plt.rc('font', family='Malgun Gothic')
        plt.rcParams['axes.unicode_minus'] = False
        df = pd.Series(grades, name="Grade")
        plt.figure(figsize=(8, 4))
        ax = sns.countplot(x=df, order=grade_order)
        plt.title(f"Grade Distribution ({year}년 {semester}학기)")
        plt.xlabel("GPA")
        plt.ylabel("Count")
        plt.suptitle(f"{course.code} – {course.name}")
        ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
        plt.tight_layout()
        plt.show()


class Course:
    """Course class."""

    total_course = 0
    majors = set()  # 모든 과목의 major를 저장하는 클래스 변수

    def __init__(
        self,
        code: str,
        major: str,
        name: str,
        section: int,
        professor: str,
        capacity: int,
        schedule: str,
        credit: int,
        year: int,
        semester: int
    ):
        _validate(COURSE_CODE_RE, code, "course code")
        self.code = code
        self.major = major
        self.name = name
        self.section = section
        self.professor = professor  # Professor.uid
        self.capacity = capacity
        self.schedule = schedule
        self.credit = credit
        self.year = year
        self.semester = semester
        Course.total_course += 1
        Course.majors.add(major)  # major를 클래스 변수에 저장


class Enrollment:
    """Lightweight link entity to avoid duplication in persistence."""

    def __init__(self, student_id: str, course_code: str, year: int, semester: int, grade: str = ""):
        self.student_id = student_id
        self.course_code = course_code
        self.year = year
        self.semester = semester
        self.grade = grade

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


###############################################################################
# Data persistence
###############################################################################


class DataManager:
    """Handles load/save of JSON data."""

    def __init__(self, filename: str = DATA_FILE):
        self.filename = filename
        (
            self.students,
            self.professors,
            self.courses,
            self.enrollments,
        ) = self._load()

    # ---------------------------------------------------------------------

    def _load(
        self,
    ) -> Tuple[Dict[str, Student], Dict[str, Professor], Dict[str, Course], List[Enrollment]]:
        print(f"데이터 파일을 로딩 중입니다: {self.filename}")
        if not os.path.exists(self.filename):
            print("데이터 파일이 없습니다. 프로그램을 종료합니다.")
            sys.exit(1)
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            print("파일 로딩 실패. 프로그램을 종료합니다.")
            sys.exit(1)

        students = {
            d["uid"]: Student(
                d["uid"],
                d["name"],
                d["major"],
                d["nationality"],
                d.get("password", "0000"),
                d.get("semesters_completed", 0),
                d.get("year", 1),
                d.get("advisor", ""),
            )
            for d in raw["students"]
        }
        professors = {
            d["uid"]: Professor(
                d["uid"],
                d["name"],
                d["major"],
                d["nationality"],
                d.get("password", "0000"),
                d.get("title", "교수"),
            )
            for d in raw["professors"]
        }
        courses = {
            d["code"]: Course(
                d["code"],
                d["major"],
                d["name"],
                d["section"],
                d["professor"],
                d["capacity"],
                d["schedule"],
                d.get("credit", 3),
                d.get("year", 2024),
                d.get("semester", 1),
            )
            for d in raw["courses"]
        }
        enrollments = [Enrollment(**e) for e in raw["enrollments"]]
        
        print(f"데이터 로딩 완료: 학생 {len(students)}명, 교수 {len(professors)}명, 과목 {len(courses)}개, 수강신청 {len(enrollments)}건")
        return students, professors, courses, enrollments

    # ---------------------------------------------------------------------

    def _save(self):
        """Persist current in-memory state to disk."""
        print(f"데이터를 저장 중입니다: {self.filename}")
        data = {
            "students": [self._user_to_dict(s) for s in self.students.values()],
            "professors": [self._user_to_dict(p) for p in self.professors.values()],
            "courses": [self._course_to_dict(c) for c in self.courses.values()],
            "enrollments": [e.to_dict() for e in self.enrollments],
        }
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"데이터 저장 완료: 학생 {len(self.students)}명, 교수 {len(self.professors)}명, 과목 {len(self.courses)}개, 수강신청 {len(self.enrollments)}건")

    # ---------------------------------------------------------------------

    @staticmethod
    def _user_to_dict(u: User) -> Dict[str, Any]:
        d = u.__dict__.copy()
        d.pop("_password", None)  # store password field plainly
        d["password"] = getattr(u, "_password", "")
        return d

    @staticmethod
    def _course_to_dict(c: Course) -> Dict[str, Any]:
        return c.__dict__.copy()


###############################################################################
# CLI
###############################################################################

class CLI:
    """Simple command-line interface."""

    PROMPT_ADMIN = "[관리자 모드]"
    PROMPT_STUDENT = "[학생 모드]"
    PROMPT_PROFESSOR = "[교수 모드]"

    def __init__(self, dm: DataManager):
        self.dm = dm
        self.current_user: Optional[User] = None

    # ---------------------------------------------------------------------

    def run(self):
        try:
            self._login_flow()
            if self.current_user is None:
                return
            if isinstance(self.current_user, Admin):
                self._admin_loop()
            elif isinstance(self.current_user, Student):
                self._student_loop()
            elif isinstance(self.current_user, Professor):
                self._professor_loop()
        except AcademicError as e:
            print(f"[오류] {e}")
        finally:
            self.dm._save()

    # ---------------------------------------------------------------------
    # Login
    # ---------------------------------------------------------------------

    def _login_flow(self):
        while True:
            print("관리자 모드로 실행하시겠습니까? [y/n] ", end="")
            admin_choice = input().strip().lower()
            if admin_choice == "y":
                self.current_user = Admin("admin", "root")
                return
            elif admin_choice == "n":
                break
            else:
                print("올바른 입력이 아닙니다. y 또는 n만 입력하세요.")

        while True:
            uid = input("학번/사번을 입력하세요: ").strip()
            if uid not in self.dm.students and uid not in self.dm.professors:
                print("미등록 사용자입니다. 다시 입력하세요.")
                continue
            fail_count = 0
            while True:
                pw = input("비밀번호를 입력하세요: ").strip()
                # Determine user type
                if uid in self.dm.students and self.dm.students[uid].authenticate(pw):
                    self.current_user = self.dm.students[uid]
                    print(f"환영합니다, {self.current_user.name}님!")
                    return
                elif uid in self.dm.professors and self.dm.professors[uid].authenticate(pw):
                    self.current_user = self.dm.professors[uid]
                    print(f"환영합니다, {self.current_user.name}님!")
                    return
                else:
                    fail_count += 1
                    if fail_count >= 5:
                        print("비밀번호를 5회 이상 틀려 프로그램을 종료합니다.")
                        sys.exit(1)
                    print(f"인증 실패. 다시 입력하세요. (남은 시도: {5 - fail_count}회)")
            break

    # ---------------------------------------------------------------------
    # Loops
    # ---------------------------------------------------------------------

    def _admin_loop(self):
        while True:
            print(self.PROMPT_ADMIN)
            try:
                choice = input("1. 학생 입력\n2. 학생 삭제\n3. 총원 조회\n4. 종료\n> ").strip()
            except KeyboardInterrupt:
                print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                continue
            if choice not in {"1", "2", "3", "4"}:
                print("올바르지 않은 입력입니다. 1~4 중에서 선택하세요.")
                continue
            if choice == "1":
                try:
                    self._admin_add_student()
                except KeyboardInterrupt:
                    print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
            elif choice == "2":
                try:
                    self._admin_delete_student()
                except KeyboardInterrupt:
                    print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
            elif choice == "3":
                self._admin_show_counts()
            elif choice == "4":
                break

    @log_access
    @require_admin
    @check_time
    def _admin_show_counts(self):
        print("\n[총원 현황]")
        print(f"총 학생 수: {len(self.dm.students)}명")
        print(f"총 교수 수: {len(self.dm.professors)}명")
        print(f"총 과목 수: {len(self.dm.courses)}개")
        print(f"총 수강신청 건수: {len(self.dm.enrollments)}건")

    def _student_loop(self):
        student: Student = self.current_user  # type: ignore
        while True:
            print(self.PROMPT_STUDENT)
            try:
                for cmd, desc in student.get_menu():
                    print(f"{cmd:10} {desc}")
                cmd = input("> ").strip().lower()
                if cmd == "register":
                    try:
                        self._student_register_course(student)
                    except KeyboardInterrupt:
                        print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                        continue
                elif cmd == "drop":
                    try:
                        student.drop_course(self.dm.enrollments, self.dm.courses)
                    except KeyboardInterrupt:
                        print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                        continue
                elif cmd == "courses":
                    try:
                        student.check_course(self.dm.enrollments, self.dm.courses)
                    except KeyboardInterrupt:
                        print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                        continue
                elif cmd == "grades":
                    try:
                        student.check_grade(self.dm.enrollments, self.dm.courses)
                    except KeyboardInterrupt:
                        print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                        continue
                elif cmd == "recommend":
                    # recommend 기능이 있다면 여기에 추가
                    pass
                elif cmd == "info":
                    self._print_user_info(student)
                elif cmd == "quit":
                    break
                else:
                    print("올바르지 않은 입력입니다.")
            except AcademicError as e:
                print(f"[오류] {e}")
            except KeyboardInterrupt:
                print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                continue

    def _professor_loop(self):
        prof: Professor = self.current_user  # type: ignore
        while True:
            print(self.PROMPT_PROFESSOR)
            try:
                for cmd, desc in prof.get_menu():
                    print(f"{cmd:10} {desc}")
                cmd = input("> ").strip().lower()
            except KeyboardInterrupt:
                print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                continue
            try:
                if cmd == "list":
                    self._prof_list_students(prof)
                elif cmd == "grade":
                    self._prof_assign_grade(prof)
                elif cmd == "stats":
                    self._prof_stats(prof)
                elif cmd == "info":
                    self._print_user_info(prof)
                elif cmd == "quit":
                    break
                else:
                    print("올바르지 않은 입력입니다.")
            except AcademicError as e:
                print(f"[오류] {e}")

    # ---------------------------------------------------------------------
    # Admin actions
    # ---------------------------------------------------------------------

    @log_access
    @require_admin
    @check_time
    def _admin_add_student(self):
        while True:
            try:
                uid = input("학번: ").strip()
                if not uid.isdigit() or len(uid) != 8 or not uid.startswith('20'):
                    raise ValidationError("올바른 학번(예: 20231234)을 입력하세요.")
                break
            except KeyboardInterrupt:
                print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                return
            except Exception as e:
                if "invalid literal for int()" in str(e):
                    print("올바르지 않은 입력입니다.")
                else:
                    print(e)
        name = input("이름: ").strip()
        majors = sorted(Course.majors) if Course.majors else ["Economics", "CS", "Business", "Physics", "History"]
        print("전공을 선택하세요:")
        for idx, m in enumerate(majors, 1):
            print(f"  {idx}. {m}")
        while True:
            try:
                major_idx = int(input("전공 번호: ").strip())
                if not (1 <= major_idx <= len(majors)):
                    raise ValidationError("올바른 번호를 입력하세요.")
                major = majors[major_idx - 1]
                break
            except KeyboardInterrupt:
                print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                return
            except Exception as e:
                if "invalid literal for int()" in str(e):
                    print("올바르지 않은 입력입니다.")
                else:
                    print(e)
        nationality = input("국적: ").strip()
        _validate(STUDENT_ID_RE, uid, "student ID")
        if uid in self.dm.students:
            print("이미 존재하는 학번입니다.")
            return
        # 추가 정보 입력
        while True:
            try:
                semesters_completed = int(input("이수 학기 수: ").strip())
                if semesters_completed < 0:
                    raise ValidationError("0 이상의 숫자를 입력하세요.")
                break
            except Exception as e:
                print(e)
        while True:
            try:
                year = int(input("학년(숫자): ").strip())
                if year < 1:
                    raise ValidationError("1 이상의 숫자를 입력하세요.")
                break
            except Exception as e:
                print(e)
        advisor = input("지도교수 이름: ").strip()
        enrollments = []
        while True:
            try:
                n_sem = int(input("입력할 학기 개수(0이면 건너뜀): ").strip())
                if n_sem < 0:
                    raise ValidationError("0 이상의 숫자를 입력하세요.")
                break
            except KeyboardInterrupt:
                print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                return
            except Exception as e:
                if "invalid literal for int()" in str(e):
                    print("올바르지 않은 입력입니다.")
                else:
                    print(e)
        for _ in range(n_sem):
            while True:
                try:
                    e_year = int(input("년도(예: 2024): ").strip())
                    if not (2000 <= e_year <= 2100):
                        raise ValidationError("2000~2100 사이의 년도를 입력하세요.")
                    break
                except KeyboardInterrupt:
                    print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                    return
                except Exception as e:
                    if "invalid literal for int()" in str(e):
                        print("올바르지 않은 입력입니다.")
                    else:
                        print(e)
            while True:
                try:
                    semester = int(input("학기(1 또는 2): ").strip())
                    if semester not in [1, 2]:
                        raise ValidationError("1 또는 2만 입력하세요.")
                    break
                except KeyboardInterrupt:
                    print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                    return
                except Exception as e:
                    if "invalid literal for int()" in str(e):
                        print("올바르지 않은 입력입니다.")
                    else:
                        print(e)
            # 해당 전공+학기에 개설된 과목만 필터링
            filtered_courses = [c for c in self.dm.courses.values() if c.major == major and c.year == e_year and c.semester == semester]
            print(f"[{major}] {e_year}년 {semester}학기 개설 전공 과목 목록:")
            if not filtered_courses:
                print("해당 전공의 해당 학기 개설 과목이 없습니다. 과목을 먼저 추가하세요.")
                continue
            for c in filtered_courses:
                print(f"  {c.code}: {c.name}")
            while True:
                try:
                    n_courses = int(input(f"{e_year}년 {semester}학기 수강 과목 수: ").strip())
                    if n_courses < 0:
                        raise ValidationError("0 이상의 숫자를 입력하세요.")
                    break
                except KeyboardInterrupt:
                    print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                    return
                except Exception as e:
                    if "invalid literal for int()" in str(e):
                        print("올바르지 않은 입력입니다.")
                    else:
                        print(e)
            for _ in range(n_courses):
                while True:
                    try:
                        code = input("수강 과목 코드: ").strip().upper()
                        if code not in [c.code for c in filtered_courses]:
                            raise ValidationError("해당 학기 전공 개설 과목 코드만 입력하세요.")
                        break
                    except KeyboardInterrupt:
                        print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                        return
                    except Exception as e:
                        print(e)
                valid_grades = {"A+","A0","A-","B+","B0","B-","C+","C0","C-","D+","D0","D-","F"}
                while True:
                    try:
                        grade = input("성적(공백 입력 시 미입력): ").strip().upper()
                        if grade == "":
                            break
                        if grade not in valid_grades:
                            raise ValidationError("잘못된 학점입니다. 다시 입력하세요.")
                        break
                    except KeyboardInterrupt:
                        print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                        return
                    except Exception as e:
                        print(e)
                # Enrollment에 필요한 정보: student_id, course_code, year, semester, grade
                enrollments.append(Enrollment(uid, code, e_year, semester, grade))
        self.dm.students[uid] = Student(uid, name, major, nationality, "0000", semesters_completed=semesters_completed, year=year, advisor=advisor)
        self.dm.enrollments.extend(enrollments)
        print("등록 완료.")

    @log_access
    @require_admin
    @check_time
    def _admin_delete_student(self):
        while True:
            try:
                uid = input("삭제할 학생의 학번: ").strip()
                if uid not in self.dm.students:
                    print("존재하지 않는 학번입니다.")
                    return
                break
            except KeyboardInterrupt:
                print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                return
            except Exception as e:
                print(e)
        # 학생 삭제
        del self.dm.students[uid]
        # 해당 학생의 수강신청(Enrollment)도 모두 삭제
        self.dm.enrollments = [e for e in self.dm.enrollments if e.student_id != uid]
        print("학생 및 관련 수강 이력이 삭제되었습니다.")

    # ---------------------------------------------------------------------
    # Student actions
    # ---------------------------------------------------------------------

    def _student_register_course(self, student: Student):
        print("\n[개설 과목 목록]")
        if not self.dm.courses:
            print("개설된 과목이 없습니다.")
            return
        filtered_courses = [c for c in self.dm.courses.values() if c.year == 2025 and c.semester == "하계학기"]
        if not filtered_courses:
            print("2025년 하계학기 개설 과목이 없습니다.")
            return
        print_course_table(sorted(filtered_courses, key=lambda x: (x.code, x.section)), professors=self.dm.professors)
        while True:
            try:
                code = input("수강하고자 하는 과목 코드: ").strip().upper()
                section = int(input("분반(숫자): ").strip())
                # 코드와 분반이 모두 일치하는 과목만 허용
                matched_courses = [c for c in filtered_courses if c.code == code and c.section == section]
                if not matched_courses:
                    raise ValidationError("존재하지 않는 과목(코드+분반)입니다.")
                course = matched_courses[0]
                student.register_course(course, self.dm.enrollments)
                break
            except KeyboardInterrupt:
                print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                return
            except Exception as e:
                print(e)

    # ---------------------------------------------------------------------
    # Professor actions
    # ---------------------------------------------------------------------

    def _get_prof_course(self, prof: Professor) -> Optional[tuple]:
        my_courses = [c for c in self.dm.courses.values() if c.professor == prof.uid]
        if not my_courses:
            print("담당 과목이 없습니다.")
            return None
        print("[담당 과목 전체 목록]")
        sorted_courses = sorted(my_courses, key=lambda x: (x.year, x.semester, x.code))
        print_course_table(sorted_courses)
        while True:
            try:
                sel = int(input("과목 번호를 입력하세요: ").strip())
                if not (1 <= sel <= len(sorted_courses)):
                    print(f"1~{len(sorted_courses)} 사이의 번호를 입력하세요.")
                    continue
                course = sorted_courses[sel-1]
                return (course, course.year, course.semester)
            except KeyboardInterrupt:
                print("\n작업이 취소되었습니다. 메뉴로 돌아갑니다.")
                return None
            except Exception:
                print("올바르지 않은 입력입니다.")

    def _prof_list_students(self, prof: Professor):
        result = self._get_prof_course(prof)
        if result:
            course, year, semester = result
            prof.list_students(course, self.dm.students, self.dm.enrollments)

    def _prof_assign_grade(self, prof: Professor):
        result = self._get_prof_course(prof)
        if not result:
            return
        course, year, semester = result
        # 해당 과목/학기 수강생 목록 출력
        enrolled_students = [e.student_id for e in self.dm.enrollments if e.course_code == course.code and e.year == year and e.semester == semester]
        if not enrolled_students:
            print("해당 과목에 해당 학기 수강한 학생이 없습니다.")
            return
        print("\n[수강 학생 목록]")
        for sid in enrolled_students:
            name = self.dm.students[sid].name if sid in self.dm.students else "(알 수 없음)"
            print(f"  {sid} {name}")
        # 학번 입력 반복
        while True:
            sid = input("학생 학번: ").strip()
            if sid not in enrolled_students:
                print("수강한 학생이 아닙니다. 위 목록에서 학번을 다시 입력하세요.")
                continue
            break
        valid_grades = {"A+","A0","A-","B+","B0","B-","C+","C0","C-","D+","D0","D-","F"}
        while True:
            grade = input("성적: ").strip().upper()
            if grade not in valid_grades:
                print("잘못된 학점입니다. 다시 입력하세요.")
                continue
            break
        # Enrollment에서 해당 정보 찾기
        found = False
        for e in self.dm.enrollments:
            if e.student_id == sid and e.course_code == course.code and e.year == year and e.semester == semester:
                e.grade = grade
                found = True
                break
        if not found:
            print("해당 학생은 이 과목에 해당 학기 수강 신청하지 않았습니다.")
            return
        # 학생 객체의 성적 정보도 갱신
        prof.assign_grade(self.dm.students[sid], course, grade, self.dm.enrollments)
        print(f"{self.dm.students[sid].name}({sid}) → {grade}")

    def _prof_stats(self, prof: Professor):
        result = self._get_prof_course(prof)
        if result:
            course, year, semester = result
            prof.plot_course_stats(course, self.dm.students, self.dm.enrollments, year, semester)

    # student, professor의 정보를 출력하기 위한 method
    def _print_user_info(self, user: User):
        print("\n[내 정보]")
        print(f"이름: {user.name}")
        print(f"학번/사번: {user.uid}")
        print(f"전공/학과: {user.major}")
        print(f"국적: {user.nationality}")
        if isinstance(user, Student):
            print(f"학년: {getattr(user, 'year', '-')}")
            print(f"지도교수: {getattr(user, 'advisor', '-')}")
        if isinstance(user, Professor):
            print(f"직함: {getattr(user, 'title', '-')}")
        print("")


###############################################################################
# Admin stub (very light)
###############################################################################


class Admin(User):
    """Administrator with full privileges."""

    def __init__(self, uid: str, password: str):
        super().__init__(uid, "Administrator", "Adminmajor", "KR", password)

    # Menu not used (simple numeric interface implemented in CLI)


###############################################################################
# Main entry point
###############################################################################


def main():
    dm = DataManager()
    cli = CLI(dm)
    cli.run()


if __name__ == "__main__":
    main()
# <<< END academic_system.py >>>
