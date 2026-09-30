from checks.code_match_check import CodeMatchCheck
from checks.text_guard_check import TextGuardCheck
from model import Assignment, DomainRuleViolation, GradeBook, Student, SubmittedWork
from vendors.code_match import CodeMatchClient, CodeMatchCloud
from vendors.text_guard import TextGuardClient, TextGuardCloud, TextGuardSource

text_guard_cloud = TextGuardCloud()
code_match_cloud = CodeMatchCloud()
text_guard = TextGuardClient(text_guard_cloud)
code_match = CodeMatchClient(code_match_cloud)

anna = Student("anna.ivanova", "Анна")
boris = Student("boris.petrov", "Борис")
vera = Student("vera.smirnova", "Вера")

text_guard_cloud.answer(
    "Эссе Анны",
    0.62,
    TextGuardSource("https://sources.example/alpha", 0.20),
    TextGuardSource("https://sources.example/beta", 0.18),
)
text_guard_cloud.answer("Эссе Бориса", 0.91)

essay = Assignment("Эссе по истории", 70, TextGuardCheck(text_guard))
essay.add(SubmittedWork(anna, "essay.docx", "Эссе Анны"))
essay.add(SubmittedWork(boris, "essay.pdf", "Эссе Бориса"))
essay.add(SubmittedWork(vera, "essay.odt", "Эссе Веры"))
text_guard_cloud.complete_all()

code_match_cloud.answer("Код Бориса", "Код Веры", 87)
code_match_cloud.answer("Код Анны", "Код Бориса", 30)

program = Assignment("Программа на Python", 25, CodeMatchCheck(code_match, "python"))
program.add(SubmittedWork(anna, "main.py", "Код Анны"))
program.add(SubmittedWork(boris, "main.py", "Код Бориса"))
program.add(SubmittedWork(vera, "main.py", "Код Веры"))
program.close()

for assignment in (essay, program):
    print(assignment.title)
    for line in GradeBook([assignment]).lines():
        print(f"  {line}")
    print()

for line in program.render(program.works[1]):
    print(line)

try:
    program.add(SubmittedWork(Student("gleb.orlov", "Глеб"), "main.py", "Код Глеба"))
except DomainRuleViolation as error:
    print(f"Работа после закрытия приёма отклонена: {error.code}")
