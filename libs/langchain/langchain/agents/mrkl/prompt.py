# flake8: noqa
PREFIX = """Ответь на следующие вопросы как можно лучше. У тебя есть следующие инструменты:"""
FORMAT_INSTRUCTIONS = """Используй следующий формат:

Вопрос: входной вопрос, на который ты должен ответить
Мысль: ты всегда должен думать о том, что делать
Действие: действие, которое следует предпринять, должно быть одним из [{tool_names}]
Ввод действия: ввод для действия
Наблюдение: результат действия
... (этот цикл Мысль/Действие/Ввод действия/Наблюдение может повторяться N раз)
Мысль: Теперь я знаю окончательный ответ
Окончательный ответ: окончательный ответ на исходный вопрос"""
SUFFIX = """Начни!

Вопрос: {input}
Мысль:{agent_scratchpad}"""
