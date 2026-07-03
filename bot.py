import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery

from config import BOT_TOKEN, MASSEUR_ID, LOG_LEVEL
from states import BookingForm, MasseurActions
from keyboards import (
    get_start_keyboard,
    get_massage_types_keyboard,
    get_confirm_keyboard,
    get_edit_keyboard,
    get_skip_keyboard,
    get_cancel_keyboard,
    get_masseur_action_keyboard,
    get_masseur_edit_keyboard
)
from booking_rules import (
    MASSAGE_TYPES,
    normalize_name,
    validate_birth_date,
    validate_booking_date,
    validate_name,
    validate_time,
)
from google_sheets import (
    save_booking,
    update_booking,
    get_user_id_by_record_number,
    init_google_sheets,
    calculate_age
)

# Настройка логирования — будем видеть что происходит в консоли
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создаём роутер для обработчиков
router = Router()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

async def delete_message_safe(bot: Bot, chat_id: int, message_id: int):
    """Безопасное удаление сообщения (не падает если уже удалено)"""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение {message_id}: {e}")


async def delete_previous_messages(bot: Bot, state: FSMContext, chat_id: int):
    """Удаляем все предыдущие сообщения бота и пользователя"""
    data = await state.get_data()
    
    # Получаем список ID сообщений для удаления
    messages_to_delete = data.get('messages_to_delete', [])
    
    for msg_id in messages_to_delete:
        await delete_message_safe(bot, chat_id, msg_id)
    
    # Очищаем список
    await state.update_data(messages_to_delete=[])


async def add_message_to_delete(state: FSMContext, message_id: int):
    """Добавляем ID сообщения в список на удаление"""
    data = await state.get_data()
    messages = data.get('messages_to_delete', [])
    messages.append(message_id)
    await state.update_data(messages_to_delete=messages)


async def ensure_masseur_access(callback: CallbackQuery) -> bool:
    """Проверяем, что действие выполняет авторизованный массажист."""
    if callback.from_user.id == MASSEUR_ID:
        return True

    logger.warning(
        "Попытка доступа к действиям массажиста от пользователя %s",
        callback.from_user.id,
    )
    await callback.answer("У вас нет доступа к этому действию.", show_alert=True)
    return False


def format_booking_card(data: dict, show_number: bool = False, record_number: int = None) -> str:
    """
    Форматируем анкету записи для отображения.
    Дата рождения показывается с возрастом в скобках.
    
    show_number: если True, показывать номер записи (для массажиста)
    record_number: номер записи
    """
    # Получаем дату рождения и считаем возраст для отображения
    birth_date = data.get('child_age', '—')
    if birth_date != '—':
        age_display = calculate_age(birth_date)
    else:
        age_display = '—'
    
    # Если нужно показать номер - добавляем его в начало
    header = "📋 <b>Анкета записи на массаж</b>"
    if show_number and record_number:
        header = f"📋 <b>Запись №{record_number}</b>"
    
    return (
        f"{header}\n\n"
        f"👤 <b>Имя родителя:</b> {data.get('parent_name', '—')}\n"
        f"👶 <b>Фамилия и имя ребенка:</b> {data.get('child_name', '—')}\n"
        f"🎂 <b>Дата рождения:</b> {age_display}\n"
        f"💆 <b>Вид массажа:</b> {data.get('massage_type', '—')}\n"
        f"📅 <b>Дата:</b> {data.get('date', '—')}\n"
        f"🕐 <b>Время:</b> {data.get('time', '—')}\n"
        f"💬 <b>Комментарий:</b> {data.get('comment', 'Нет комментария')}\n"
    )


# ============================================================
# СТАРТОВЫЙ ОБРАБОТЧИК
# ============================================================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    
    # Сбрасываем состояние если было
    await state.clear()
    
    # Удаляем сообщение пользователя с командой /start
    await delete_message_safe(message.bot, message.chat.id, message.message_id)
    
    # Отправляем приветственное сообщение с кнопкой
    sent = await message.answer(
        text=(
            "👋 Добро пожаловать!\n\n"
            "Я помогу записать вашего ребенка на массаж. "
            "Нажмите кнопку ниже чтобы начать запись:"
        ),
        reply_markup=get_start_keyboard()
    )
    
    # Сохраняем ID сообщения для последующего удаления
    await state.update_data(messages_to_delete=[sent.message_id])


# ============================================================
# НАЧАЛО ЗАПИСИ
# ============================================================

@router.callback_query(F.data == "start_booking")
async def start_booking(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал 'Записаться на массаж'"""
    
    # Удаляем предыдущие сообщения
    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    
    # Удаляем само сообщение с кнопкой
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)
    
    # Отправляем запрос имени родителя
    sent = await callback.message.answer(
        text=(
            "📝 <b>Шаг 1 из 7</b>\n\n"
            "Введите <b>Фамилию и имя родителя</b>:"
        ),
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    
    await add_message_to_delete(state, sent.message_id)
    
    # Переводим в состояние ожидания имени родителя
    await state.set_state(BookingForm.parent_name)
    
    await callback.answer()  # Убираем "часики" на кнопке


# ============================================================
# ОТМЕНА ЗАПИСИ
# ============================================================

@router.callback_query(F.data == "cancel_booking")
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


# ============================================================
# ШАГ 1: ИМЯ РОДИТЕЛЯ
# ============================================================

@router.message(BookingForm.parent_name)
async def process_parent_name(message: Message, state: FSMContext):
    """Получаем имя родителя"""

    # Сохраняем сообщение пользователя для удаления
    await add_message_to_delete(state, message.message_id)

    parent_name = normalize_name(message.text)
    if not validate_name(parent_name):
        sent = await message.answer(
            "⚠️ Пожалуйста, введите корректное имя (минимум 2 символа):",
            reply_markup=get_cancel_keyboard()
        )
        await add_message_to_delete(state, sent.message_id)
        return

    # Сохраняем имя родителя
    await state.update_data(parent_name=parent_name)

    if await check_editing_and_proceed(message, state):
        return

    await delete_previous_messages(message.bot, state, message.chat.id)

    # Просим фамилию и имя ребенка
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
    """Получаем имя ребенка"""

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
# ШАГ 3: ВОЗРАСТ РЕБЕНКА
# ============================================================

@router.message(BookingForm.child_age)
async def process_child_age(message: Message, state: FSMContext):
    """
    Получаем дату рождения ребенка.
    Проверяем что дата введена в формате ДД.ММ.ГГГГ
    и что дата рождения не в будущем.
    """

    await add_message_to_delete(state, message.message_id)

    birth_date_text = message.text.strip()
    is_valid_birth_date, birth_date_error = validate_birth_date(birth_date_text)
    if not is_valid_birth_date:
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
            error_messages[birth_date_error],
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        await add_message_to_delete(state, sent.message_id)
        return

    await state.update_data(child_age=birth_date_text)

    if await check_editing_and_proceed(message, state):
        return

    await delete_previous_messages(message.bot, state, message.chat.id)

    # Переходим к выбору вида массажа
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
    """Пользователь выбрал вид массажа"""

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

    # Просим дату
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
# ШАГ 5: ДАТА
# ============================================================

@router.message(BookingForm.date)
async def process_date(message: Message, state: FSMContext):
    """Получаем желаемую дату"""

    await add_message_to_delete(state, message.message_id)

    date_text = message.text.strip()
    is_valid_booking_date, booking_date_error = validate_booking_date(date_text)
    if not is_valid_booking_date:
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
            error_messages[booking_date_error],
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
    """
    Получаем желаемое время.
    Принимаем форматы: 10:30 или 10.30
    Сохраняем всегда в формате 10:30
    """

    await add_message_to_delete(state, message.message_id)

    is_valid_time, time_normalized = validate_time(message.text)
    if not is_valid_time:
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
    """Получаем комментарий"""

    await add_message_to_delete(state, message.message_id)
    await state.update_data(comment=message.text.strip())

    if await check_editing_and_proceed(message, state):
        return

    await delete_previous_messages(message.bot, state, message.chat.id)
    await show_booking_card(message, state)


@router.callback_query(BookingForm.comment, F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext):
    """Пользователь пропустил комментарий"""

    await state.update_data(comment="Нет комментария")

    if await check_editing_and_proceed(callback, state):
        await callback.answer()
        return

    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)

    await show_booking_card(callback.message, state)
    await callback.answer()


async def show_booking_card(message: Message, state: FSMContext):
    """Показываем итоговую анкету пользователю"""
    
    data = await state.get_data()
    card_text = format_booking_card(data)
    
    sent = await message.answer(
        text=(
            f"{card_text}\n"
            "Проверьте данные. Всё верно?"
        ),
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard()
    )
    
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(BookingForm.confirm)


# ============================================================
# ШАГ 8: ПОДТВЕРЖДЕНИЕ
# ============================================================

@router.callback_query(BookingForm.confirm, F.data == "confirm_yes")
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    """Пользователь подтвердил запись"""
    
    data = await state.get_data()
    data['user_id'] = callback.from_user.id
    data['username'] = callback.from_user.username or ''  # Может быть None если нет username
    
    # Удаляем все сообщения
    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)
    
    # Сохраняем в Google Таблицу
    record_number = await save_booking(data)
    
    if record_number and isinstance(record_number, int):
        # Успешное сохранение - record_number содержит номер записи
        
        # Уведомляем пользователя об успехе
        sent = await callback.message.answer(
            text=(
                "✅ <b>Запись успешно оформлена!</b>\n\n"
                "Мы свяжемся с вами для подтверждения записи.\n"
                "Спасибо, что выбрали нас! 💆"
            ),
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )
        
        # Используем номер записи как booking_id для редактирования
        booking_id = str(record_number)
        
        # Отправляем уведомление массажисту с кнопками (включая номер записи)
        card_text = format_booking_card(data, show_number=True, record_number=record_number)
        user_info = f"@{callback.from_user.username}" if callback.from_user.username else f"ID: {callback.from_user.id}"
        
        masseur_message = await callback.bot.send_message(
            chat_id=MASSEUR_ID,
            text=(
                f"🔔 <b>Новая запись на массаж!</b>\n\n"
                f"{card_text}\n"
                f"👤 <b>Telegram клиента:</b> {user_info}"
            ),
            parse_mode="HTML",
            reply_markup=get_masseur_action_keyboard(booking_id)
        )
        
        # Сохраняем информацию о сообщении массажисту и пользователя для дальнейшей обработки
        await state.update_data(
            booking_id=booking_id,
            record_number=record_number,
            masseur_message_id=masseur_message.message_id,
            user_message_chat_id=callback.message.chat.id,
            user_data=data
        )
        
    else:
        # Ошибка сохранения
        sent = await callback.message.answer(
            text=(
                "❌ <b>Произошла ошибка при сохранении записи.</b>\n\n"
                "Пожалуйста, попробуйте ещё раз или свяжитесь с нами напрямую."
            ),
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )
    
    await state.clear()
    await state.update_data(messages_to_delete=[sent.message_id])
    await callback.answer()


# ============================================================
# РЕДАКТИРОВАНИЕ АНКЕТЫ
# ============================================================

@router.callback_query(BookingForm.confirm, F.data == "confirm_edit")
async def edit_booking(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет внести изменения"""
    
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


@router.callback_query(BookingForm.edit_choice, F.data.startswith("edit_"))
async def process_edit_choice(callback: CallbackQuery, state: FSMContext):
    """Обрабатываем выбор поля для редактирования"""
    
    await delete_previous_messages(callback.bot, state, callback.message.chat.id)
    await delete_message_safe(callback.bot, callback.message.chat.id, callback.message.message_id)
    
    # Определяем что нужно изменить
    edit_map = {
        "edit_parent_name": (BookingForm.parent_name, "👤 Введите новое <b>имя родителя</b>:"),
        "edit_child_name": (BookingForm.child_name, "👶 Введите новое <b>имя ребенка</b>:"),
        "edit_child_age": (BookingForm.child_age, "🎂 Введите новую <b>дату рождения ребенка</b> (ДД.ММ.ГГГГ):"),
        "edit_massage_type": (BookingForm.massage_type, "💆 Выберите новый <b>вид массажа</b>:"),
        "edit_date": (BookingForm.date, "📅 Введите новую <b>дату</b> (ДД.ММ.ГГГГ):"),
        "edit_time": (BookingForm.time, "🕐 Введите новое <b>время</b> (ЧЧ:ММ):"),
        "edit_comment": (BookingForm.comment, "💬 Введите новый <b>комментарий</b>:"),
    }
    
    new_state, prompt_text = edit_map[callback.data]
    
    # Для вида массажа показываем кнопки
    if callback.data == "edit_massage_type":
        sent = await callback.message.answer(
            text=prompt_text,
            parse_mode="HTML",
            reply_markup=get_massage_types_keyboard()
        )
    elif callback.data == "edit_comment":
        sent = await callback.message.answer(
            text=prompt_text,
            parse_mode="HTML",
            reply_markup=get_skip_keyboard()
        )
    else:
        sent = await callback.message.answer(
            text=prompt_text,
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
    
    await add_message_to_delete(state, sent.message_id)
    await state.set_state(new_state)
    
    # Помечаем что идёт редактирование (чтобы вернуться к анкете)
    await state.update_data(is_editing=True)
    await callback.answer()


# ============================================================
# ДЕЙСТВИЯ МАССАЖИСТА: ПОДТВЕРЖДЕНИЕ ЗАПИСИ
# ============================================================

@router.callback_query(F.data.startswith("masseur_confirm_"))
async def masseur_confirm_booking(callback: CallbackQuery, bot: Bot):
    """Массажист подтвердил запись"""

    if not await ensure_masseur_access(callback):
        return

    record_number = int(callback.data.replace("masseur_confirm_", ""))
    user_id = await get_user_id_by_record_number(record_number)
    if not user_id:
        await callback.answer("❌ Не удалось найти клиента для этой записи", show_alert=True)
        return

    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "✅ <b>Ваша запись подтверждена!</b>\n\n"
                "Массажист принял вашу заявку.\n"
                "Если у вас есть какие-либо вопросы, пожалуйста, свяжитесь с массажистом Дарьей.\n\n"
                "Спасибо за выбор! 💆"
            ),
            parse_mode="HTML"
        )
        
        # Редактируем сообщение для массажиста удалив кнопки
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=(
                f"{callback.message.text}\n\n"
                "✅ <b>Запись подтверждена!</b> (отправлено уведомление клиенту)"
            ),
            parse_mode="HTML",
            reply_markup=None  # Удаляем кнопки
        )
        
        await callback.answer("✅ Запись подтверждена! Клиент получил уведомление.")
        
    except Exception as e:
        logger.error(f"Ошибка при подтверждении записи: {e}")
        await callback.answer("❌ Ошибка при отправке уведомления клиенту.")


# ============================================================
# ДЕЙСТВИЯ МАССАЖИСТА: РЕДАКТИРОВАНИЕ ЗАПИСИ
# ============================================================

@router.callback_query(F.data.startswith("masseur_edit_"))
async def masseur_edit_booking(callback: CallbackQuery, state: FSMContext):
    """Массажист хочет редактировать запись"""

    if not await ensure_masseur_access(callback):
        return

    booking_id = callback.data.replace("masseur_edit_", "")
    record_number = int(booking_id)

    user_id = await get_user_id_by_record_number(record_number)
    if not user_id:
        await callback.answer("❌ Ошибка: не удалось найти клиента для этой записи")
        return

    await state.set_state(MasseurActions.massage_edit_choice)
    await state.update_data(
        booking_id=booking_id,
        record_number=record_number,
        user_id=user_id,
        masseur_message_id=callback.message.message_id,
        original_message_text=callback.message.text,
        edited_fields={}  # Инициализируем словарь отредактированных данных
    )
    
    # Редактируем сообщение массажисту
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=f"{callback.message.text}\n\n✏️ <b>Режим редактирования:</b> Выберите что редактировать:",
        parse_mode="HTML",
        reply_markup=get_masseur_edit_keyboard(booking_id)
    )
    
    await callback.answer()


@router.callback_query(MasseurActions.massage_edit_choice, F.data.startswith("medit_"))
async def massage_edit_field(callback: CallbackQuery, state: FSMContext):
    """Массажист выбрал поле для редактирования"""

    if not await ensure_masseur_access(callback):
        return

    data = await state.get_data()
    booking_id = data.get('booking_id')  # Это номер записи
    user_id = data.get('user_id')  # ID клиента для отправки уведомления
    record_number = int(booking_id) if booking_id else None
    
    # Определяем что редактируем
    if callback.data.startswith("medit_done_"):
        # Завершить редактирование - обновить данные в таблице и отправить уведомления
        edited_fields = data.get('edited_fields', {})
        
        # Обновляем данные в Google Sheets по номеру записи
        if edited_fields and record_number:
            success = await update_booking(record_number, edited_fields)
            if not success:
                await callback.answer("❌ Ошибка при обновлении данных в таблице")
                return
        
        # Отправляем уведомление клиенту
        if user_id:
            try:
                await callback.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "📝 <b>Ваша запись была отредактирована и подтверждена!</b>\n\n"
                        "Массажист внес необходимые изменения в вашу заявку.\n"
                        "Спасибо за выбор! 💆"
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления клиенту: {e}")
        
        # Редактируем финальное сообщение массажисту
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=(
                f"{data.get('original_message_text', '')}\n\n"
                "✏️ <b>Запись отредактирована и подтверждена!</b> (клиент уведомлен)"
            ),
            parse_mode="HTML",
            reply_markup=None
        )
        
        await state.clear()
        await callback.answer("✅ Редактирование завершено! Клиент уведомлен.")
        return
    
    # Для других полей показываем форму редактирования
    edit_prompts = {
        "medit_parent_name_": "👤 Введите новое <b>имя родителя</b>:",
        "medit_child_name_": "👶 Введите новое <b>имя ребенка</b>:",
        "medit_child_age_": "🎂 Введите новую <b>дату рождения</b> (ДД.ММ.ГГГГ):",
        "medit_massage_type_": "💆 Выберите новый <b>вид массажа</b>:",
        "medit_date_": "📅 Введите новую <b>дату</b> (ДД.ММ.ГГГГ):",
        "medit_comment_": "💬 Введите новый <b>комментарий</b>:",
    }
    
    for prefix, prompt in edit_prompts.items():
        if callback.data.startswith(prefix):
            field_type = prefix.replace("medit_", "").rstrip("_")
            
            # Сохраняем какое поле редактируем
            await state.update_data(editing_field=field_type)
            
            if field_type == "massage_type":
                await callback.bot.send_message(
                    chat_id=callback.from_user.id,
                    text=prompt,
                    parse_mode="HTML",
                    reply_markup=get_massage_types_keyboard()
                )
                await state.set_state(MasseurActions.massage_edit_field)
            elif field_type == "date":
                await callback.bot.send_message(
                    chat_id=callback.from_user.id,
                    text="📅 Введите новую <b>дату и время</b>:\nДата (ДД.ММ.ГГГГ):",
                    parse_mode="HTML"
                )
                await state.set_state(MasseurActions.massage_edit_field)
            else:
                await callback.bot.send_message(
                    chat_id=callback.from_user.id,
                    text=prompt,
                    parse_mode="HTML"
                )
                await state.set_state(MasseurActions.massage_edit_field)
            
            break
    
    await callback.answer()


@router.message(MasseurActions.massage_edit_field)
async def process_masseur_edit_input(message: Message, state: FSMContext):
    """Обрабатываем ввод отредактированного поля от массажиста"""

    data = await state.get_data()
    field = data.get('editing_field')
    booking_id = data.get('booking_id')

    edited_fields = data.get('edited_fields', {})

    if field == "child_age":
        birth_date_text = message.text.strip()
        is_valid_birth_date, birth_date_error = validate_birth_date(birth_date_text)
        if not is_valid_birth_date:
            error_messages = {
                "invalid_format": (
                    "⚠️ Неверный формат даты рождения.\n"
                    "Введите дату в формате <b>ДД.ММ.ГГГГ</b>\n"
                    "Примеры: <b>15.03.2020</b> или <b>10.10.2024</b>"
                ),
                "future": (
                    "⚠️ Дата рождения не может быть в будущем.\n"
                    "Пожалуйста, введите корректную дату в формате <b>ДД.ММ.ГГГГ</b>"
                ),
                "too_old": (
                    "⚠️ Возраст ребенка не может быть больше 18 лет.\n"
                    "Пожалуйста, введите корректную дату рождения в формате <b>ДД.ММ.ГГГГ</b>"
                ),
            }
            await message.answer(
                error_messages[birth_date_error],
                parse_mode="HTML"
            )
            return

        edited_fields['child_age'] = birth_date_text
        await state.update_data(edited_fields=edited_fields)
        await message.answer(
            "✅ Дата рождения обновлена!\nВыберите дальнейшее действие:",
            parse_mode="HTML",
            reply_markup=get_masseur_edit_keyboard(booking_id)
        )
        await state.set_state(MasseurActions.massage_edit_choice)
        return

    if field == "date":
        date_text = message.text.strip()
        is_valid_booking_date, booking_date_error = validate_booking_date(date_text)
        if not is_valid_booking_date:
            error_messages = {
                "invalid_format": (
                    "⚠️ Неверный формат даты.\n"
                    "Введите дату в формате <b>ДД.ММ.ГГГГ</b>\n"
                    "Примеры: <b>20.04.2026</b> или <b>01.05.2026</b>"
                ),
                "past": (
                    "⚠️ Дата не может быть в прошлом.\n"
                    "Пожалуйста, введите корректную дату в формате <b>ДД.ММ.ГГГГ</b>"
                ),
            }
            await message.answer(
                error_messages[booking_date_error],
                parse_mode="HTML"
            )
            return

        edited_fields['date'] = date_text
        await state.update_data(edited_fields=edited_fields)
        await message.answer(
            "🕐 Теперь введите <b>время</b> (ЧЧ:ММ):",
            parse_mode="HTML"
        )
        await state.set_state(MasseurActions.massage_edit_time)
        return

    if field in {"parent_name", "child_name"}:
        normalized = normalize_name(message.text)
        if not validate_name(normalized):
            await message.answer(
                "⚠️ Пожалуйста, введите корректное имя.",
                parse_mode="HTML"
            )
            return
        edited_fields[field] = normalized
    elif field == "comment":
        edited_fields[field] = message.text.strip()
    else:
        edited_fields[field] = message.text.strip()
    await state.update_data(edited_fields=edited_fields)

    await message.answer(
        "✅ Поле обновлено!\nВыберите дальнейшее действие:",
        parse_mode="HTML",
        reply_markup=get_masseur_edit_keyboard(booking_id)
    )
    
    await state.set_state(MasseurActions.massage_edit_choice)


@router.message(MasseurActions.massage_edit_time)
async def process_masseur_edit_time(message: Message, state: FSMContext):
    """Обрабатываем ввод времени при редактировании даты"""

    is_valid_time, time_normalized = validate_time(message.text)
    if not is_valid_time:
        await message.answer(
            "⚠️ Неверный формат времени.\n"
            "Введите время в формате <b>ЧЧ:ММ</b> или <b>ЧЧ.ММ</b>\n\n"
            "Примеры: <b>10:30</b> или <b>10.30</b>",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    booking_id = data.get('booking_id')

    edited_fields = data.get('edited_fields', {})
    edited_fields['time'] = time_normalized
    await state.update_data(edited_fields=edited_fields)

    await message.answer(
        "✅ Дата и время обновлены!\nВыберите дальнейшее действие:",
        parse_mode="HTML",
        reply_markup=get_masseur_edit_keyboard(booking_id)
    )
    
    await state.set_state(MasseurActions.massage_edit_choice)


@router.callback_query(MasseurActions.massage_edit_field, F.data.startswith("massage_"))
async def masseur_massage_type_select(callback: CallbackQuery, state: FSMContext):
    """Массажист выбрал вид массажа при редактировании"""

    if not await ensure_masseur_access(callback):
        return

    massage_name = MASSAGE_TYPES.get(callback.data)
    if not massage_name:
        await callback.answer("❌ Неизвестный вид массажа", show_alert=True)
        return

    data = await state.get_data()
    booking_id = data.get('booking_id')

    if data.get('editing_field') != 'massage_type':
        await callback.answer("❌ Поле для редактирования не выбрано", show_alert=True)
        return

    edited_fields = data.get('edited_fields', {})
    edited_fields['massage_type'] = massage_name
    await state.update_data(edited_fields=edited_fields)

    await callback.answer(f"✅ {massage_name} выбран")
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text="✅ Поле обновлено!\nВыберите дальнейшее действие:",
        parse_mode="HTML",
        reply_markup=get_masseur_edit_keyboard(booking_id)
    )

    await state.set_state(MasseurActions.massage_edit_choice)


# ============================================================
# ЗАПУСК БОТА
# ============================================================

# Флаг редактирования — проверяем в обработчиках полей
# Если is_editing=True — после ввода показываем анкету снова

# Модифицированные обработчики с поддержкой редактирования
# Добавь эту проверку в конец каждого обработчика поля:

async def check_editing_and_proceed(message_or_callback, state: FSMContext):
    """Если идёт редактирование — показываем анкету, иначе — следующий шаг"""
    data = await state.get_data()
    if data.get('is_editing'):
        if isinstance(message_or_callback, Message):
            bot = message_or_callback.bot
            chat_id = message_or_callback.chat.id
            target_message = message_or_callback
        else:
            bot = message_or_callback.bot
            chat_id = message_or_callback.message.chat.id
            target_message = message_or_callback.message

        await delete_previous_messages(bot, state, chat_id)
        await state.update_data(is_editing=False)
        await show_booking_card(target_message, state)
        return True
    return False

async def main():
    """Главная функция запуска бота"""
    
    # Инициализируем Google Sheets при запуске
    logger.info("🔧 Инициализация системы...")
    if not await init_google_sheets():
        logger.error("❌ Ошибка инициализации Google Sheets! Бот не запущен.")
        return
    
    # Создаём объект бота
    bot = Bot(token=BOT_TOKEN)
    
    # Создаём диспетчер с хранилищем состояний в памяти
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрируем роутер
    dp.include_router(router)
    
    # Удаляем старые сообщения которые пришли пока бот не работал
    await bot.delete_webhook(drop_pending_updates=True)
    
    logger.info("🤖 Бот успешно запущен!")
    logger.info("⏳ Бот ожидает сообщений...")
    
    try:
        # Запускаем бота (бесконечный цикл обработки сообщений)
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("⏸ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка в работе бота: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("❌ Бот остановлен")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
