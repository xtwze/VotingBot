# Создайте новый файл или добавьте в начало user.py
import random

NUM_WORDS = {
    0: "ноль", 1: "один", 2: "два", 3: "три", 4: "четыре",
    5: "пять", 6: "шесть", 7: "семь", 8: "восемь", 9: "девять",
}


def generate_captcha():
    a, b = random.randint(1, 9), random.randint(1, 9)
    operation = random.choice(['+', '-'])

    if operation == '-':
        if a < b: a, b = b, a
        answer = a - b
    else:
        answer = a + b

    question = f"Сколько будет {NUM_WORDS[a]} {operation} {NUM_WORDS[b]}? (ответ цифрой)"
    return question, answer