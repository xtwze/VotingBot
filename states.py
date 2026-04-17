from aiogram.fsm.state import State, StatesGroup


class CreatePoll(StatesGroup):
    waiting_title = State()
    adding_options = State()
    waiting_artist_name = State()


class VoteConfirm(StatesGroup):
    confirming = State()


class Broadcast(StatesGroup):
    waiting_text = State()
    confirming = State()


class CaptchaState(StatesGroup):
    waiting_answer = State()