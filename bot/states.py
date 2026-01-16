from aiogram.fsm.state import State, StatesGroup

class CreateQuiz(StatesGroup):
    waiting_title = State()
    waiting_description = State()

    waiting_questions = State()      # 👈 yangi: savollarni kutish
    q_text = State()
    opt_a = State()
    opt_b = State()
    opt_c = State()
    opt_d = State()
    correct = State()
    explanation = State()
