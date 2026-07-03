"""
Хендлеры пользователя: /start, начало записи, отмена.
"""
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import MASSEUR_ID
from states import BookingForm
from keyboards import (
    get_start_keyboard,
    get_cancel_keyboard,
)
from handlers.common import (
    delete_message_safe,
    delete_previous_messages,
    add_message_to_delete,
)
from callbacks import BookingAction

router = Router(name="user_start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    await delete_message_safe(message.bot, message.chat.id, message.message_id)

    sent = await message.answer(
        text=(
            "👋 Добро пожаловать!\n\n"
            "Я помогу записать вашего ребенка на массаж. "
            "Нажмите кнопку ниже чтобы начать запись:"
        ),
        reply_markup=get_start_keyboard()
    )
    await state.update_data(messages_to_delete=[sent.message_id])


@router.callback_query(BookingAction.filter(F.action == "start"))
async def start_booking(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал 'Записаться на массаж'"""
    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)

    sent = await callback.message.answer(
        text=(
            "📝 <b>Шаг 1 из 7</b>\n\n"
            "Введите <b>Фамилию и имя родителя</b>:"
        ),
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(BookingForm.parent_name)
    await callback.answer()


@router.callback_query(BookingAction.filter(F.action == "cancel"))
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    """Пользователь отменил запись"""
    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)

    await state.clear()

    sent = await callback.message.answer(
        text="❌ Запись отменена.\n\nЧтобы начать снова, нажмите кнопку:",
        reply_markup=get_start_keyboard()
    )
    await state.update_data(messages_to_delete=[sent.message_id])
    await callback.answer()