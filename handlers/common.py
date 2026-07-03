"""
Общие утилиты: безопасное удаление сообщений, работа с FSM-списком сообщений на удаление.
"""
import logging
from typing import List

from aiogram import Bot
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)


async def delete_message_safe(bot: Bot, chat_id: int, message_id: int) -> bool:
    """
    Безопасное удаление сообщения (не падает если уже удалено или нет прав).
    Возвращает True если удалено, False если ошибка.
    """
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение {message_id} в чате {chat_id}: {e}")
        return False


async def delete_previous_messages(bot: Bot, state: FSMContext, chat_id: int) -> int:
    """
    Удаляет все предыдущие сообщения бота и пользователя, сохранённые в FSM.
    Возвращает количество успешно удалённых сообщений.
    """
    data = await state.get_data()
    messages_to_delete: List[int] = data.get('messages_to_delete', [])

    deleted_count = 0
    for msg_id in messages_to_delete:
        if await delete_message_safe(bot, chat_id, msg_id):
            deleted_count += 1

    # Очищаем список
    await state.update_data(messages_to_delete=[])
    return deleted_count


async def add_message_to_delete(state: FSMContext, message_id: int) -> None:
    """Добавляет ID сообщения в список на удаление."""
    data = await state.get_data()
    messages: List[int] = data.get('messages_to_delete', [])
    messages.append(message_id)
    await state.update_data(messages_to_delete=messages)


async def ensure_masseur_access(callback, masseur_id: int) -> bool:
    """
    Проверяет, что действие выполняет авторизованный массажист.
    Возвращает True если доступ есть, False если нет (и отправляет alert).
    """
    if callback.from_user.id == masseur_id:
        return True

    logger.warning(
        "Попытка доступа к действиям массажиста от пользователя %s",
        callback.from_user.id,
    )
    await callback.answer("У вас нет доступа к этому действию.", show_alert=True)
    return False


def format_booking_card(data: dict, show_number: bool = False, record_number: int = None) -> str:
    """
    Форматирует анкету записи для отображения.
    Дата рождения показывается с возрастом в скобках.
    """
    from google_sheets import calculate_age

    birth_date = data.get('child_age', '—')
    if birth_date != '—':
        age_display = calculate_age(birth_date)
    else:
        age_display = '—'

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