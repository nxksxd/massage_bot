from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from booking_rules import MASSAGE_TYPE_OPTIONS


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Стартовая кнопка - Записаться на массаж"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="💆 Записаться на массаж",
            callback_data="start_booking"
        )
    )
    return builder.as_markup()


def get_massage_types_keyboard() -> InlineKeyboardMarkup:
    """Кнопки выбора вида массажа"""
    builder = InlineKeyboardBuilder()

    for callback_data, button_text, _ in MASSAGE_TYPE_OPTIONS:
        builder.add(InlineKeyboardButton(text=button_text, callback_data=callback_data))
    
    # Располагаем по 1 кнопке в ряд
    builder.adjust(1)
    return builder.as_markup()


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Кнопки подтверждения анкеты"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Всё верно!", callback_data="confirm_yes"),
        InlineKeyboardButton(text="✏️ Внести изменения", callback_data="confirm_edit")
    )
    builder.adjust(1)  # По одной кнопке в ряд
    return builder.as_markup()


def get_edit_keyboard() -> InlineKeyboardMarkup:
    """Кнопки для выбора что именно редактировать"""
    builder = InlineKeyboardBuilder()
    
    fields = [
        ("👤 Изменить имя родителя", "edit_parent_name"),
        ("👶 Изменить имя ребенка", "edit_child_name"),
        ("🎂 Изменить возраст ребенка", "edit_child_age"),
        ("💆 Изменить вид массажа", "edit_massage_type"),
        ("📅 Изменить дату", "edit_date"),
        ("🕐 Изменить время", "edit_time"),
        ("💬 Изменить комментарий", "edit_comment"),
    ]
    
    for text, callback in fields:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback))
    
    builder.adjust(1)
    return builder.as_markup()


def get_skip_keyboard() -> InlineKeyboardMarkup:
    """Кнопка пропустить (для комментария)"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_comment")
    )
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel_booking")
    )
    return builder.as_markup()


def get_masseur_action_keyboard(booking_id: str) -> InlineKeyboardMarkup:
    """Кнопки для массажиста: Подтвердить или Редактировать запись"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="✅ Подтвердить запись",
            callback_data=f"masseur_confirm_{booking_id}"
        )
    )
    builder.add(
        InlineKeyboardButton(
            text="✏️ Редактировать запись",
            callback_data=f"masseur_edit_{booking_id}"
        )
    )
    builder.adjust(1)
    return builder.as_markup()


def get_masseur_edit_keyboard(booking_id: str) -> InlineKeyboardMarkup:
    """Кнопки для выбора что редактировать (для массажиста)"""
    builder = InlineKeyboardBuilder()
    
    fields = [
        ("👤 Имя родителя", f"medit_parent_name_{booking_id}"),
        ("👶 Имя ребенка", f"medit_child_name_{booking_id}"),
        ("🎂 Возраст ребенка", f"medit_child_age_{booking_id}"),
        ("💆 Вид массажа", f"medit_massage_type_{booking_id}"),
        ("📅 Дата и время", f"medit_date_{booking_id}"),
        ("💬 Комментарий", f"medit_comment_{booking_id}"),
        ("✅ Завершить редактирование", f"medit_done_{booking_id}"),
    ]
    
    for text, callback in fields:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback))
    
    builder.adjust(1)
    return builder.as_markup()
