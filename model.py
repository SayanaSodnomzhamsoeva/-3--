"""Предметная модель. Ничего не знает о поставщиках проверки (см. пакет checks)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable, Protocol


class DomainRuleViolation(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class Student:
    def __init__(self, login: str, name: str) -> None:
        if not login.strip() or not name.strip():
            raise DomainRuleViolation("student-invalid", "The student login and name must not be empty.")
        self.login = login
        self.name = name


class SubmittedWork:
    def __init__(self, student: Student, file_name: str, content: str) -> None:
        if not file_name.strip() or not content:
            raise DomainRuleViolation("work-file-invalid", "The work needs a file name and non-empty content.")
        self.student = student
        self.file_name = file_name
        self.content = content


class CheckStatus(Enum):
    NOT_FINISHED = "not_finished"
    IMPOSSIBLE = "impossible"
    DONE = "done"


@dataclass(frozen=True)
class Match:
    """source — готовый к показу источник: адрес документа или «работа студента …»."""
    percent: int
    source: str


@dataclass(frozen=True)
class CheckResult:
    """Результат проверки в терминах предметной области — без кодов и типов поставщиков."""
    status: CheckStatus
    originality: int | None = None
    matches: tuple[Match, ...] = ()
    is_suspicious: bool = False

    @staticmethod
    def unfinished() -> "CheckResult":
        return CheckResult(CheckStatus.NOT_FINISHED)

    @staticmethod
    def not_possible() -> "CheckResult":
        return CheckResult(CheckStatus.IMPOSSIBLE)

    @staticmethod
    def completed(originality: int, matches: Iterable[Match]) -> "CheckResult":
        return CheckResult(CheckStatus.DONE, originality, tuple(matches))


class OriginalityCheck(Protocol):
    """«checkFunc» со схемы: способ проверки, выбираемый для задания."""

    def submit(self, work: SubmittedWork) -> None:
        """Работа принята в задание."""

    def close(self) -> None:
        """Приём работ по заданию закрыт."""

    def check(self, work: SubmittedWork) -> CheckResult:
        """Текущий результат проверки. Временный сбой сервиса обрабатывается внутри."""


class Assignment:
    def __init__(self, title: str, min_originality: int, check_func: OriginalityCheck) -> None:
        if not title.strip():
            raise DomainRuleViolation("assignment-title-empty", "The assignment title must not be empty.")
        if not 0 <= min_originality <= 100:
            raise DomainRuleViolation("min-originality-invalid", "The minimal originality must be between 0 and 100.")
        self.title = title
        self.min_originality = min_originality  # ниже этого значения работа подозрительна
        self._check_func = check_func
        self._works: list[SubmittedWork] = []
        self.is_closed = False

    @property
    def works(self) -> tuple[SubmittedWork, ...]:
        return tuple(self._works)

    def add(self, work: SubmittedWork) -> None:
        if self.is_closed:
            raise DomainRuleViolation("submissions-closed", "The assignment no longer accepts works.")
        self._check_func.submit(work)
        self._works.append(work)

    def close(self) -> None:
        if self.is_closed:
            return
        self.is_closed = True
        self._check_func.close()

    def check(self, work: SubmittedWork) -> CheckResult:
        """Итог проверки с учётом минимального процента оригинальности задания."""
        if work not in self._works:
            raise ValueError("The work does not belong to this assignment.")
        result = self._check_func.check(work)
        if result.status is CheckStatus.DONE:
            assert result.originality is not None
            return replace(result, is_suspicious=result.originality < self.min_originality)
        return result

    def render(self, work: SubmittedWork) -> list[str]:
        """Карточка работы для преподавателя."""
        lines = [f"{work.student.name} | {work.file_name}"]
        result = self.check(work)

        if result.status is CheckStatus.DONE:
            verdict = "подозрительно" if result.is_suspicious else "без замечаний"
            lines.append(f"Проверка: готово, оригинальность {result.originality}%, {verdict}")
            for match in sorted(result.matches, key=lambda m: m.percent, reverse=True):
                lines.append(f"Совпадение {match.percent}%: {match.source}")
        elif result.status is CheckStatus.IMPOSSIBLE:
            lines.append("Проверка: невозможна, формат не поддерживается")
        else:
            lines.append("Проверка: не завершена")
        return lines


class GradeBook:
    def __init__(self, assignments: Iterable[Assignment]) -> None:
        self._assignments = list(assignments)

    def lines(self) -> list[str]:
        rows: list[str] = []
        for assignment in self._assignments:
            for work in assignment.works:
                result = assignment.check(work)
                if result.status is CheckStatus.DONE:
                    originality = f"{result.originality}%"
                    mark = "подозрительно" if result.is_suspicious else "без замечаний"
                elif result.status is CheckStatus.IMPOSSIBLE:
                    originality, mark = "—", "проверка невозможна"
                else:
                    originality, mark = "—", "проверка не завершена"
                rows.append(f"{work.student.name} | {work.file_name} | {originality} | {mark}")
        return rows
