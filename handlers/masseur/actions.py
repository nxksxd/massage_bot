"""
Хендлеры массажиста: подтверждение/редактирование записей.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import MASSEUR_ID
from states import MasseurActions
from google_sheets import update_booking, get_user_id_by_record_number
from keyboards import (
    get_masseur_action_keyboard,
    get_masseur_edit_keyboard,
)
from handlers.common import (
    delete_previous_messages,
    delete_message_safe,
    add_message_to_delete,
    format_booking_card,
    ensure_masseur_access,
)
from callbacks import MasseurAction, MasseurEditField

router = Router(name="masseur_actions")


@router.callback_query(MasseurAction.filter(F.action == "confirm"))
async def masseur_confirm(callback: CallbackQuery, callback_data: MasseurAction, state: FSMContext):
    """Массажист подтверждает запись"""
    if not await ensure_masseur_access(callback, MASSEUR_ID):
        return

    record_id = callback_data.record_id

    # Обновляем статус в таблице (добавляем пометку "подтверждено" в комментарий или отдельное поле)
    # Пока просто уведомляем пользователя
    user_id = await get_user_id_by_record_number(record_id)

    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)

    if user_id:
        try:
            await callback.bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ <b>Ваша запись №{record_id} подтверждена массажистом!</b>\n\n"
                    f"Ждём вас на сеансе. Если возникнут вопросы — пишите."
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            # Пользователь мог заблокировать бота
            pass

    sent = await callback.message.answer(
        text=f"✅ Запись #{record_id} подтверждена. Уведомление отправлено клиенту.",
        reply_markup=get_start_keyboard()
    )
    await add_message_to_delete(state, sent.message_id)
    await callback.answer("✅ Подтверждено")


@router.callback_query(MasseurAction.filter(F.action == "edit"))
async def masseur_edit(callback: CallbackQuery, callback_data: MasseurAction, state: FSMContext):
    """Массажист начинает редактирование записи"""
    if not await ensure_masseur_access(callback, MASSEUR_ID):
        return

    record_id = callback_data.record_id
    await state.update_data(masseur_record_id=record_id)

    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)

    sent = await callback.message.answer(
        text=f"✏️ <b>Редактирование записи #{record_id}</b>\n\nЧто хотите изменить?",
        parse_mode="HTML",
        reply_markup=get_masseur_edit_keyboard(record_id)
    )
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(MasseurActions.massage_edit_choice)
    await callback.answer()


@router.callback_query(MasseurActions.massage_edit_choice, MasseurEditField.filter())
async def masseur_edit_field(callback: CallbackQuery, callback_data: MasseurEditField, state: FSMContext):
    """Выбор поля для редактирования массажистом"""
    if not await ensure_masseur_access(callback, MASSEUR_ID):
        return

    field = callback_data.field
    record_id = callback_data.record_id

    if field == "done":
        await masseur_edit_done(callback, state)
        return

    field_prompts = {
        "parent_name": ("Имя родителя", "Введите новое имя родителя:"),
        "child_name": ("Имя ребенка", "Введите новое имя ребенка:"),
        "child_age": ("Возраст ребенка", "Введите дату рождения (ДД.ММ.ГГГГ):"),
        "massage_type": ("Вид массажа", "Выберите новый вид массажа:"),
        "date_time": ("Дата и время", "Введите новую дату (ДД.ММ.ГГГГ):"),
        "comment": ("Комментарий", "Введите новый комментарий:"),
    }

    if field not in field_prompts:
        await callback.answer("❌ Неизвестное поле", show_alert=True)
        return

    label, prompt = field_prompts[field]
    await state.update_data(masseur_editing_field=field)

    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)

    from keyboards import get_massage_types_keyboard, get_cancel_keyboard

    if field == "massage_type":
        sent = await callback.message.answer(
            text=f"📝 <b>Изменение: {label}</b>\n\n{prompt}",
            parse_mode="HTML",
            reply_markup=get_massage_types_keyboard()
        )
    else:
        sent = await callback.message.answer(
            text=f"📝 <b>Изменение: {label}</b>\n\n{prompt}",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )

    await add_message_to_delete(state, sent.message_id)
    await state.set_state(MasseurActions.massage_edit_field)
    await callback.answer()


@router.message(MasseurActions.massage_edit_field)
async def masseur_process_edit_field(message: Message, state: FSMContext):
    """Обработка ввода нового значения поля массажистом"""
    data = await state.get_data()
    field = data.get('masseur_editing_field')
    record_id = data.get('masseur_record_id')

    if not field or not record_id:
        await message.answer("❌ Ошибка: потерян контекст редактирования. Начните заново.")
        await state.clear()
        return

    # Валидация и нормализация значения
    from booking_rules import (
        normalize_name,
        validate_name,
        validate_birth_date,
        validate_booking_date,
        validate_time,
    )
    from google_sheets import calculate_age

    new_value = message.text.strip()

    if field in {"parent_name", "child_name"}:
        if not validate_name(new_value):
            await message.answer("⚠️ Некорректное имя. Минимум 2 символа:", reply_markup=get_cancel_keyboard())
            return
        new_value = normalize_name(new_value)

    elif field == "child_age":
        is_valid, _ = validate_birth_date(new_value)
        if not is_valid:
            await message.answer("⚠️ Неверный формат даты. ДД.ММ.ГГГГ:", reply_markup=get_cancel_keyboard())
            return
        new_value = calculate_age(new_value)

    elif field == "date_time":
        is_valid, _ = validate_booking_date(new_value)
        if not is_valid:
            await message.answer("⚠️ Неверный формат даты. ДД.ММ.ГГГГ:", reply_markup=get_cancel_keyboard())
            return

    elif field == "time":
        from booking_rules import validate_time as vt
        is_valid, normalized = vt(new_value)
        if not is_valid:
            await message.answer("⚠️ Неверный формат времени. ЧЧ:ММ:", reply_markup=get_cancel_keyboard())
            return
        new_value = normalized
        field = "time"  # в таблице колонка time

    # Обновляем в Google Sheets
    success = await update_booking(record_id, {field: new_value})

    await delete_previous_messages(message.bot, state, message.chat.id)

    if success:
        sent = await message.answer(
            text=f"✅ Поле «{field}» обновлено для записи #{record_id}.",
            reply_markup=get_masseur_edit_keyboard(record_id)
        )
    else:
        sent = await message.answer(
            text=f"❌ Ошибка при обновлении. Попробуйте позже.",
            reply_markup=get_masseur_edit_keyboard(record_id)
        )

    await add_message_to_delete(state, sent.message_id)
    await state.set_state(MasseurActions.massage_edit_choice)


@router.callback_query(MasseurActions.massage_edit_choice, MasseurEditField.filter(F.field == "done"))
async def masseur_edit_done(callback: CallbackQuery, state: FSMContext):
    """Завершение редактирования массажистом"""
    if not await ensure_masseur_access(callback, MASSEUR_ID):
        return

    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)

    await state.clear()

    sent = await callback.message.answer(
        text="✅ Редактирование завершено.",
        reply_markup=get_start_keyboard()
    )
    await add_message_to_delete(state, sent.message_id)
    await callback.answer()