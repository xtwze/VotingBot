# Создайте новый файл или добавьте в начало user.py
import random

# Словарный запас символов-двойников для обхода простых парсеров
NUM_WORDS = {
    0: "нοль",      # ο - греческая омикрон
    1: "οдuн",      # ο - греческая, u - латинская
    2: "дβa",       # β - греческая бета, a - латинская
    3: "mрu",       # m - латинская, u - латинская
    4: "чεmыpe",    # ε - греческая эпсилон, m, p, e - латинские
    5: "nяmь",      # n, m - латинские
    6: "ωecmь",     # ω - греческая омега, e, c, m - латинские
    7: "ceмь",      # c, e - латинские
    8: "вοceмь",    # ο, c, e - латинские
    9: "дeβяmь",    # e - латиница, β - бета, m - латиница
    10: "дecяmь"    # e, c, m - латиница
}

# Функция для дополнительного зашумления (вставка невидимого символа между буквами)
def obfuscate(text: str) -> str:
    # Вставляет невидимый разделитель Zero Width Space между каждой буквой
    return "\u200B".join(list(text))


def generate_captcha():
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    operation = random.choice(['+', '-'])

    if operation == '-':
        if a < b: a, b = b, a
        answer = a - b
    else:
        answer = a + b

    # Берем слова из хардкорного словаря и накладываем невидимый шум
    word_a = obfuscate(NUM_WORDS[a])
    word_b = obfuscate(NUM_WORDS[b])

    op_text = "nлюc" if operation == "+" else "muнyc"
    op_text = obfuscate(op_text)

    question = f"Сколько будет: {word_a} {op_text} {word_b} ? (ответ пришлите цифрой)🤓"
    return question, answer