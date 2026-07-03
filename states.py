# Состояния — это "шаги" разговора бота с пользователем
# Бот запоминает на каком шаге находится каждый пользователь

from aiogram.fsm.state import State, StatesGroup


class BookingForm(StatesGroup):
    # Каждый State — это один шаг заполнения анкеты
    parent_name = State()    # Шаг 1: имя родителя
    child_name = State()     # Шаг 2: имя ребенка
    child_age = State()      # Шаг 3: возраст ребенка
    massage_type = State()   # Шаг 4: вид массажа
    date = State()           # Шаг 5: дата
    time = State()           # Шаг 6: время
    comment = State()        # Шаг 7: комментарий
    confirm = State()        # Шаг 8: подтверждение анкеты
    edit_choice = State()    # Шаг 9: выбор что редактировать


class MasseurActions(StatesGroup):
    # Состояния для действий массажиста
    massage_confirm = State()      # Ожидание действия (подтвердить/редактировать)
    massage_edit_choice = State()  # Выбор что редактировать
    massage_edit_field = State()   # Редактирование поля
    massage_edit_time = State()    # Редактирование времени (после даты)