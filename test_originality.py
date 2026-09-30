import unittest

from checks.code_match_check import CodeMatchCheck
from checks.text_guard_check import TextGuardCheck
from model import Assignment, DomainRuleViolation, GradeBook, Student, SubmittedWork
from vendors.code_match import CodeMatchClient, CodeMatchCloud
from vendors.text_guard import TextGuardClient, TextGuardCloud, TextGuardSource


class OriginalityTests(unittest.TestCase):
    def setUp(self):
        self.tg_cloud = TextGuardCloud()
        self.cm_cloud = CodeMatchCloud()
        self.anna = Student("anna.ivanova", "Анна")
        self.boris = Student("boris.petrov", "Борис")
        self.vera = Student("vera.smirnova", "Вера")

    # Создание объектов: сценарии и ожидаемые строки от устройства модели не зависят.

    def text_assignment(self, min_originality):
        return Assignment("Эссе", min_originality, TextGuardCheck(TextGuardClient(self.tg_cloud)))

    def code_assignment(self, min_originality, language="python"):
        return Assignment("Программа", min_originality, CodeMatchCheck(CodeMatchClient(self.cm_cloud), language))

    @staticmethod
    def submit(assignment, student, file_name, content):
        work = SubmittedWork(student, file_name, content)
        assignment.add(work)
        return work

    # Сценарии

    def test_card_of_text_work_below_min_originality_shows_suspicion_and_sources(self):
        self.tg_cloud.answer(
            "Эссе Анны", 0.62,
            TextGuardSource("https://sources.example/beta", 0.18),
            TextGuardSource("https://sources.example/alpha", 0.20),
        )
        essay = self.text_assignment(70)
        work = self.submit(essay, self.anna, "essay.docx", "Эссе Анны")
        self.tg_cloud.complete_all()

        self.assertEqual(essay.render(work), [
            "Анна | essay.docx",
            "Проверка: готово, оригинальность 62%, подозрительно",
            "Совпадение 20%: https://sources.example/alpha",
            "Совпадение 18%: https://sources.example/beta",
        ])

    def test_card_of_code_work_names_the_student_with_similar_work(self):
        self.cm_cloud.answer("Код Бориса", "Код Веры", 87)
        self.cm_cloud.answer("Код Анны", "Код Бориса", 30)
        program = self.code_assignment(25)
        self.submit(program, self.anna, "main.py", "Код Анны")
        boris_work = self.submit(program, self.boris, "main.py", "Код Бориса")
        self.submit(program, self.vera, "main.py", "Код Веры")
        program.close()

        self.assertEqual(program.render(boris_work), [
            "Борис | main.py",
            "Проверка: готово, оригинальность 13%, подозрительно",
            "Совпадение 87%: работа студента Вера",
            "Совпадение 30%: работа студента Анна",
        ])

    def test_gradebook_shows_completed_unfinished_and_impossible_checks(self):
        self.tg_cloud.answer("Эссе Анны", 0.62)
        self.tg_cloud.answer("Эссе Бориса", 0.70)
        essay = self.text_assignment(70)
        self.submit(essay, self.anna, "essay.docx", "Эссе Анны")
        self.submit(essay, self.boris, "essay.pdf", "Эссе Бориса")
        self.submit(essay, self.vera, "essay.odt", "Эссе Веры")
        self.tg_cloud.complete_all()
        self.submit(essay, Student("gleb.orlov", "Глеб"), "essay.txt", "Эссе Глеба")

        self.assertEqual(GradeBook([essay]).lines(), [
            "Анна | essay.docx | 62% | подозрительно",
            "Борис | essay.pdf | 70% | без замечаний",
            "Вера | essay.odt | — | проверка невозможна",
            "Глеб | essay.txt | — | проверка не завершена",
        ])

    def test_code_check_is_not_finished_until_submissions_are_closed(self):
        program = self.code_assignment(25)
        work = self.submit(program, self.anna, "main.py", "Код Анны")

        self.assertEqual(program.render(work), ["Анна | main.py", "Проверка: не завершена"])

    def test_work_after_closing_submissions_is_rejected(self):
        program = self.code_assignment(25)
        self.submit(program, self.anna, "main.py", "Код Анны")
        program.close()

        with self.assertRaises(DomainRuleViolation) as error:
            self.submit(program, self.boris, "main.py", "Код Бориса")

        self.assertEqual(error.exception.code, "submissions-closed")

    def test_failed_text_check_is_restarted_without_teacher(self):
        self.tg_cloud.answer("Эссе Анны", 0.62)
        self.tg_cloud.fail_once("Эссе Анны")
        essay = self.text_assignment(70)
        work = self.submit(essay, self.anna, "essay.docx", "Эссе Анны")
        self.tg_cloud.complete_all()  # первая обработка завершилась сбоем

        self.assertEqual(essay.render(work), ["Анна | essay.docx", "Проверка: не завершена"])  # здесь перезапуск

        self.tg_cloud.complete_all()

        self.assertEqual(essay.render(work), [
            "Анна | essay.docx",
            "Проверка: готово, оригинальность 62%, подозрительно",
        ])

    def test_code_work_without_matches_is_fully_original(self):
        program = self.code_assignment(25)
        work = self.submit(program, self.anna, "main.py", "Код Анны")
        self.submit(program, self.boris, "main.py", "Код Бориса")
        program.close()

        self.assertEqual(program.render(work), [
            "Анна | main.py",
            "Проверка: готово, оригинальность 100%, без замечаний",
        ])

    def test_originality_is_rounded_down(self):
        self.tg_cloud.answer("Эссе Анны", 0.29)  # 0.29 * 100 в float даёт 28.999...
        essay = self.text_assignment(70)
        work = self.submit(essay, self.anna, "essay.txt", "Эссе Анны")
        self.tg_cloud.complete_all()

        self.assertTrue(essay.render(work)[1].startswith("Проверка: готово, оригинальность 29%"))

    def test_code_assignment_needs_language(self):
        with self.assertRaises(DomainRuleViolation) as error:
            self.code_assignment(25, language=" ")

        self.assertEqual(error.exception.code, "code-language-missing")


if __name__ == "__main__":
    unittest.main()
