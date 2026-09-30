"""Адаптер TextGuard: асинхронная проверка, каждая работа — отдельная задача в очереди."""
from decimal import Decimal

from model import CheckResult, Match, SubmittedWork
from vendors.text_guard import TextGuardClient, TextGuardFlags, TextGuardStatus


def _to_percent(share: float) -> int:
    # Доли приходят с точностью до сотых; проценты округляются вниз.
    # Decimal(str(...)) защищает от ошибок двоичных дробей (0.29 * 100 = 28.999...).
    return int(Decimal(str(share)) * 100)


class TextGuardCheck:
    def __init__(self, client: TextGuardClient) -> None:
        self._client = client
        self._jobs: dict[SubmittedWork, str] = {}

    def submit(self, work: SubmittedWork) -> None:
        # Университет не учитывает цитаты и список литературы.
        self._jobs[work] = self._client.upload(
            work.file_name,
            work.content,
            TextGuardFlags.EXCLUDE_QUOTES | TextGuardFlags.EXCLUDE_BIBLIOGRAPHY,
        )

    def close(self) -> None:
        pass  # тексты проверяются независимо, закрытие приёма ничего не меняет

    def check(self, work: SubmittedWork) -> CheckResult:
        job_id = self._jobs[work]
        status = self._client.get_status(job_id)

        if status == TextGuardStatus.FAILED:
            self._client.restart(job_id)  # временный сбой: без участия преподавателя
            return CheckResult.unfinished()
        if status == TextGuardStatus.REJECTED:
            return CheckResult.not_possible()
        if status != TextGuardStatus.DONE:
            return CheckResult.unfinished()

        report = self._client.get_report(job_id)
        matches = [Match(_to_percent(s.share), s.url) for s in report.sources]
        return CheckResult.completed(_to_percent(report.uniqueness), matches)
