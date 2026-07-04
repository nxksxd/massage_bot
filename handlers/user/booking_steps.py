"""
Хендлеры пользователя: пошаговая запись (7 шагов FSM).
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import MASSEUR_ID
from states import BookingForm
from booking_rules import (
    MASSAGE_TYPES,
    normalize_name,
    validate_birth_date,
    validate_booking_date,
    validate_name,
    validate_time,
)
from keyboards import (
    get_start_keyboard,
    get_masseur_action_keyboard,
    get_massage_types_keyboard,
    get_confirm_keyboard,
    get_edit_keyboard,
    get_skip_keyboard,
    get_cancel_keyboard,
)
from handlers.common import (
    delete_previous_messages,
    delete_message_safe,
    add_message_to_delete,
    format_booking_card,
)
from callbacks import BookingAction, EditField

router = Router(name="user_booking_steps")


# ============================================================
# ШАГ 1: ИМЯ РОДИТЕЛЯ
# ============================================================
@router.message(BookingForm.parent_name)
async def process_parent_name(message: Message, state: FSMContext):
    await add_message_to_delete(state, message.message_id)

    parent_name = normalize_name(message.text)
    if not validate_name(parent_name):
        sent = await message.answer(
            "⚠️ Пожалуйста, введите корректное имя (минимум 2 символа):",
            reply_markup=get_cancel_keyboard()
        )
        await add_message_to_delete(state, sent.message_id)
        return

    await state.update_data(parent_name=parent_name)

    if await check_editing_and_proceed(message, state):
        return

    await delete_previous_messages(message.bot, state, message.chat.id)

    sent = await message.answer(
        text=(
            "📝 <b>Шаг 2 из 7</b>\n\n"
            "Введите <b>фамилию и имя ребенка</b>\n"
            "Например: <i>Иванов Петя</i>"
        ),
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(BookingForm.child_name)


# ============================================================
# ШАГ 2: ИМЯ РЕБЕНКА
# ============================================================
@router.message(BookingForm.child_name)
async def process_child_name(message: Message, state: FSMContext):
    await add_message_to_delete(state, message.message_id)

    child_name = normalize_name(message.text)
    if not validate_name(child_name):
        sent = await message.answer(
            "⚠️ Пожалуйста, введите корректное имя ребенка:",
            reply_markup=get_cancel_keyboard()
        )
        await add_message_to_delete(state, sent.message_id)
        return

    await state.update_data(child_name=child_name)

    if await check_editing_and_proceed(message, state):
        return

    await delete_previous_messages(message.bot, state, message.chat.id)

    sent = await message.answer(
        text=(
            "📝 <b>Шаг 3 из 7</b>\n\n"
            "Введите <b>дату рождения ребенка</b>\n"
            "Формат: ДД.ММ.ГГГГ\n"
            "Например: <b>15.03.2020</b>"
        ),
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(BookingForm.child_age)


# ============================================================
# ШАГ 3: ДАТА РОЖДЕНИЯ (ВОЗРАСТ)
# ============================================================
@router.message(BookingForm.child_age)
async def process_child_age(message: Message, state: FSMContext):
    await add_message_to_delete(state, message.message_id)

    birth_date_text = message.text.strip()
    is_valid, error_code = validate_birth_date(birth_date_text)

    if not is_valid:
        data = await state.get_data()
        msgs = data.get('messages_to_delete', [])
        for msg_id in msgs[:-1]:
            await delete_message_safe(message.bot, message.chat.id, msg_id)

        error_messages = {
            "invalid_format": (
                "⚠️ Неверный формат даты рождения.\n"
                "Пожалуйста, введите дату в формате <b>ДД.ММ.ГГГГ</b>\n"
                "Например: <b>15.03.2020</b>"
            ),
            "future": (
                "⚠️ Дата рождения не может быть в будущем.\n"
                "Пожалуйста, введите корректную дату в формате <b>ДД.ММ.ГГГГ</b>"
            ),
            "too_old": (
                "⚠️ Возраст ребенка не может быть больше 18 лет.\n"
                "Пожалуйста, проверьте дату рождения:"
            ),
        }
        sent = await message.answer(
            error_messages[error_code],
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        await add_message_to_delete(state, sent.message_id)
        return

    await state.update_data(child_age=birth_date_text)

    if await check_editing_and_proceed(message, state):
        return

    await delete_previous_messages(message.bot, state, message.chat.id)

    sent = await message.answer(
        text=(
            "📝 <b>Шаг 4 из 7</b>\n\n"
            "Выберите <b>вид массажа</b>:"
        ),
        parse_mode="HTML",
        reply_markup=get_massage_types_keyboard()
    )
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(BookingForm.massage_type)


# ============================================================
# ШАГ 4: ВИД МАССАЖА (через кнопки)
# ============================================================
@router.callback_query(BookingForm.massage_type, F.data.startswith("massage_"))
async def process_massage_type(callback: CallbackQuery, state: FSMContext):
    massage_name = MASSAGE_TYPES.get(callback.data)
    if not massage_name:
        await callback.answer("❌ Неизвестный вид массажа", show_alert=True)
        return

    await state.update_data(massage_type=massage_name)

    if await check_editing_and_proceed(callback, state):
        await callback.answer(f"✅ {massage_name} выбран")
        return

    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)

    sent = await callback.message.answer(
        text=(
            "📝 <b>Шаг 5 из 7</b>\n\n"
            "Введите <b>желаемую дату</b> сеанса\n"
            "Формат: ДД.ММ.ГГГГ (например: 25.12.2026):"
        ),
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(BookingForm.date)
    await callback.answer()


# ============================================================
# ШАГ 5: ДАТА СЕАНСА
# ============================================================
@router.message(BookingForm.date)
async def process_date(message: Message, state: FSMContext):
    await add_message_to_delete(state, message.message_id)

    date_text = message.text.strip()
    is_valid, error_code = validate_booking_date(date_text)

    if not is_valid:
        data = await state.get_data()
        msgs = data.get('messages_to_delete', [])
        for msg_id in msgs[:-1]:
            await delete_message_safe(message.bot, message.chat.id, msg_id)

        error_messages = {
            "invalid_format": (
                "⚠️ Неверный формат даты.\n"
                "Пожалуйста, введите дату в формате <b>ДД.ММ.ГГГГ</b>\n"
                "Например: <b>25.12.2026</b>"
            ),
            "past": (
                "⚠️ Дата сеанса не может быть в прошлом.\n"
                "Пожалуйста, введите актуальную дату в формате <b>ДД.ММ.ГГГГ</b>"
            ),
        }
        sent = await message.answer(
            error_messages[error_code],
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        await add_message_to_delete(state, sent.message_id)
        return

    await state.update_data(date=date_text)

    if await check_editing_and_proceed(message, state):
        return

    await delete_previous_messages(message.bot, state, message.chat.id)

    sent = await message.answer(
        text=(
            "📝 <b>Шаг 6 из 7</b>\n\n"
            "Введите <b>желаемое время</b> сеанса\n"
            "Можно писать через <b>:</b> или через <b>.</b>\n"
            "Например: <b>10:30</b> или <b>10.30</b>"
        ),
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(BookingForm.time)


# ============================================================
# ШАГ 6: ВРЕМЯ
# ============================================================
@router.message(BookingForm.time)
async def process_time(message: Message, state: FSMContext):
    await add_message_to_delete(state, message.message_id)

    is_valid, time_normalized = validate_time(message.text)
    if not is_valid:
        data = await state.get_data()
        msgs = data.get('messages_to_delete', [])
        for msg_id in msgs[:-1]:
            await delete_message_safe(message.bot, message.chat.id, msg_id)

        sent = await message.answer(
            "⚠️ Неверный формат времени.\n"
            "Введите время в формате <b>ЧЧ:ММ</b> или <b>ЧЧ.ММ</b>\n\n"
            "Примеры: <b>10:30</b> или <b>10.30</b>",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        await add_message_to_delete(state, sent.message_id)
        return

    await state.update_data(time=time_normalized)

    if await check_editing_and_proceed(message, state):
        return

    await delete_previous_messages(message.bot, state, message.chat.id)

    sent = await message.answer(
        text=(
            "📝 <b>Шаг 7 из 7</b>\n\n"
            "Введите <b>комментарий</b> к записи\n"
            "(особые пожелания, вопросы, уточнения)\n\n"
            "Или нажмите кнопку чтобы пропустить:"
        ),
        parse_mode="HTML",
        reply_markup=get_skip_keyboard()
    )
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(BookingForm.comment)


# ============================================================
# ШАГ 7: КОММЕНТАРИЙ
# ============================================================
@router.message(BookingForm.comment)
async def process_comment(message: Message, state: FSMContext):
    await add_message_to_delete(state, message.message_id)
    await state.update_data(comment=message.text.strip())

    if await check_editing_and_proceed(message, state):
        return

    await show_confirmation(message, state)


@router.callback_query(BookingForm.comment, BookingAction.filter(F.action == "skip"))
async def skip_comment(callback: CallbackQuery, state: FSMContext):
    await state.update_data(comment="")
    if await check_editing_and_proceed(callback, state):
        await callback.answer()
        return
    await show_confirmation(callback, state)
    await callback.answer()


# ============================================================
# ПОДТВЕРЖДЕНИЕ АНКЕТЫ
# ============================================================
async def show_confirmation(event, state: FSMContext):
    """Показывает заполненную анкету для подтверждения."""
    data = await state.get_data()
    text = format_booking_card(data) + "\n<b>Всё верно?</b>"

    if isinstance(event, Message):
        await delete_previous_messages(event.bot, state, event.chat.id)
        sent = await event.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_confirm_keyboard()
        )
    else:  # CallbackQuery
        await delete_previous_messages(event.bot, state, event.message.chat.id)
        await delete_message_safe(event.bot, event.message.chat.id, event.message.message_id)
        sent = await event.message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_confirm_keyboard()
        )
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(BookingForm.confirm)


@router.callback_query(BookingForm.confirm, BookingAction.filter(F.action == "confirm"))
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    """Подтверждение записи — сохраняем в Google Sheets и уведомляем массажиста"""
    from google_sheets import save_booking
    from config import MASSEUR_ID
    
    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)

    data = await state.get_data()
    data['user_id'] = callback.from_user.id
    data['username'] = callback.from_user.username

    # Сохраняем запись
    record_number = await save_booking(data)

    if record_number:
        # Сообщение пользователю об успешной записи
        user_message = await callback.message.answer(
            text=(
                f"✅ <b>Запись успешно создана!</b>\n\n"
                f"📋 <b>Номер записи:</b> #{record_number}\n\n"
                f"Массажист получит уведомление и подтвердит запись.\n"
                f"Вы получите уведомление когда запись будет подтверждена."
            ),
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )
        
        # Уведомление массажисту (админу)
        try:
            masseur_text = (
                f"📋 <b>Новая запись #{record_number}</b>\n\n"
                f"👤 <b>Родитель:</b> {data.get('parent_name', 'N/A')}\n"
                f"👶 <b>Ребенок:</b> {data.get('child_name', 'N/A')}\n"
                f"🎂 <b>Возраст:</b> {data.get('child_age', 'N/A')}\n"
                f"💆 <b>Массаж:</b> {data.get('massage_type', 'N/A')}\n"
                f"📅 <b>Дата:</b> {data.get('date', 'N/A')}\n"
                f"🕐 <b>Время:</b> {data.get('time', 'N/A')}\n"
                f"💬 <b>Комментарий:</b> {data.get('comment', 'Нет')}\n\n"
                f"👤 <b>Клиент:</b> @{data.get('username', 'anonymous')} (ID: {data.get('user_id')})"
            )
            await callback.bot.send_message(
                chat_id=MASSEUR_ID,
                text=masseur_text,
                parse_mode="HTML",
                reply_markup=get_masseur_action_keyboard(record_number)
            )
        except Exception as e:
            import logging
            logging.error(f"❌ Не удалось отправить уведомление массажисту: {e}")
        
        await state.clear()
        await state.update_data(messages_to_delete=[user_message.message_id])
    else:
        error_message = await callback.message.answer(
            text=(
                "❌ <b>Ошибка при сохранении записи</b>\n\n"
                "Попробуйте позже или обратитесь к массажисту напрямую."
            ),
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )
        await state.clear()
        await state.update_data(messages_to_delete=[error_message.message_id])

    await callback.answer()


@router.callback_query(BookingForm.confirm, BookingAction.filter(F.action == "edit"))
async def edit_booking(callback: CallbackQuery, state: FSMContext):
    """Переход к редактированию"""
    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)

    sent = await callback.message.answer(
        text="✏️ <b>Что хотите изменить?</b>",
        parse_mode="HTML",
        reply_markup=get_edit_keyboard()
    )
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(BookingForm.edit_choice)
    await callback.answer()


# ============================================================
# РЕДАКТИРОВАНИЕ ПОЛЕЙ
# ============================================================
@router.callback_query(BookingForm.edit_choice, EditField.filter())
async def edit_field_choice(callback: CallbackQuery, callback_data: EditField, state: FSMContext):
    """Выбор поля для редактирования"""
    field = callback_data.field
    field_labels = {
        "parent_name": ("Имя родителя", BookingForm.parent_name, "Введите Фамилию и имя родителя:"),
        "child_name": ("Имя ребенка", BookingForm.child_name, "Введите фамилию и имя ребенка:"),
        "child_age": ("Возраст ребенка", BookingForm.child_age, "Введите дату рождения (ДД.ММ.ГГГГ):"),
        "massage_type": ("Вид массажа", BookingForm.massage_type, "Выберите вид массажа:"),
        "date": ("Дата", BookingForm.date, "Введите дату сеанса (ДД.ММ.ГГГГ):"),
        "time": ("Время", BookingForm.time, "Введите время сеанса (ЧЧ:ММ):"),
        "comment": ("Комментарий", BookingForm.comment, "Введите комментарий или нажмите пропустить:"),
    }

    if field not in field_labels:
        await callback.answer("❌ Неизвестное поле", show_alert=True)
        return

    label, next_state, prompt = field_labels[field]
    await state.update_data(editing_field=field)

    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)

    if field == "massage_type":
        sent = await callback.message.answer(
            text=f"📝 <b>Изменение: {label}</b>\n\n{prompt}",
            parse_mode="HTML",
            reply_markup=get_massage_types_keyboard()
        )
    elif field == "comment":
        sent = await callback.message.answer(
            text=f"📝 <b>Изменение: {label}</b>\n\n{prompt}",
            parse_mode="HTML",
            reply_markup=get_skip_keyboard()
        )
    else:
        sent = await callback.message.answer(
            text=f"📝 <b>Изменение: {label}</b>\n\n{prompt}",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )

    await add_message_to_delete(state, sent.message_id)
    await state.set_state(next_state)
    await callback.answer()


async def check_editing_and_proceed(event, state: FSMContext) -> bool:
    """
    Проверяет, не в режиме ли мы редактирования.
    Если да — показывает подтверждение сразу, не переходит к следующему шагу.
    """
    data = await state.get_data()
    if data.get('editing_mode'):
        await state.update_data(editing_mode=False, editing_field=None)
        await show_confirmation(event, state)
        return True
    return False