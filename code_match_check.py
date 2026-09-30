"""Адаптер CodeMatch: пакетная проверка, работы сравниваются между собой после закрытия приёма."""
from model import CheckResult, DomainRuleViolation, Match, SubmittedWork
from vendors.code_match import CodeMatchClient


def _key_of(work: SubmittedWork) -> str:
    return work.student.login.replace(".", "_")  # CodeMatch не принимает точку в ключе


class CodeMatchCheck:
    def __init__(self, client: CodeMatchClient, language: str) -> None:
        if not language or not language.strip():
            raise DomainRuleViolation("code-language-missing", "A code assignment needs a programming language.")
        self._client = client
        self._language = language
        self._batch_id: str | None = None
        self._works_by_key: dict[str, SubmittedWork] = {}

    def submit(self, work: SubmittedWork) -> None:
        if self._batch_id is None:
            self._batch_id = self._client.create_batch(self._language)
        key = _key_of(work)
        self._client.add_file(self._batch_id, key, work.content)
        self._works_by_key[key] = work

    def close(self) -> None:
        # Пакет запускается, когда собраны все работы.
        if self._batch_id is not None:
            self._client.run(self._batch_id)

    def check(self, work: SubmittedWork) -> CheckResult:
        if self._batch_id is None or not self._client.is_finished(self._batch_id):
            return CheckResult.unfinished()

        key = _key_of(work)
        pairs = sorted(
            (p for p in self._client.get_pairs(self._batch_id) if key in (p.key_a, p.key_b)),
            key=lambda p: p.percent,
            reverse=True,
        )
        matches = []
        for pair in pairs:
            other_key = pair.key_b if pair.key_a == key else pair.key_a
            other = self._works_by_key[other_key]
            matches.append(Match(pair.percent, f"работа студента {other.student.name}"))

        # Оригинальность кода — 100 минус наибольшая похожесть на работу другого студента.
        originality = 100 - (pairs[0].percent if pairs else 0)
        return CheckResult.completed(originality, matches)
