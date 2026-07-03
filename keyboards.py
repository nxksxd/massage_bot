"""
Клавиатуры бота — все inline-кнопки с CallbackData фабриками.
"""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from booking_rules import MASSAGE_TYPE_OPTIONS
from callbacks import (
    BookingAction,
    EditField,
    MasseurAction,
    MasseurEditField,
)


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Стартовая кнопка - Записаться на массаж"""
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="📅 Записаться на массаж", callback_data=BookingAction(action="start").pack())
    )
    return builder.as_markup()


def get_massage_types_keyboard() -> InlineKeyboardMarkup:
    """Кнопки выбора вида массажа"""
    builder = InlineKeyboardBuilder()

    for callback_data, button_text, _ in MASSAGE_TYPE_OPTIONS:
        builder.add(
            InlineKeyboardButton(text=button_text, callback_data=callback_data)
        )

    # Располагаем по 1 кнопке в ряд
    builder.adjust(1)
    return builder.as_markup()


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Кнопки подтверждения анкеты"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Всё верно!", callback_data=BookingAction(action="confirm").pack()),
        InlineKeyboardButton(text="✏️ Внести изменения", callback_data=BookingAction(action="edit").pack())
    )
    builder.adjust(1)
    return builder.as_markup()


def get_edit_keyboard() -> InlineKeyboardMarkup:
    """Кнопки для выбора что именно редактировать"""
    builder = InlineKeyboardBuilder()

    fields = [
        ("👤 Изменить имя родителя", "parent_name"),
        ("👶 Изменить имя ребенка", "child_name"),
        ("🎂 Изменить возраст ребенка", "child_age"),
        ("💆 Изменить вид массажа", "massage_type"),
        ("📅 Изменить дату", "date"),
        ("🕐 Изменить время", "time"),
        ("💬 Изменить комментарий", "comment"),
    ]

    for text, field in fields:
        builder.add(
            InlineKeyboardButton(text=text, callback_data=EditField(field=field).pack())
    )

    builder.adjust(1)
    return builder.as_markup()


def get_skip_keyboard() -> InlineKeyboardMarkup:
    """Кнопка пропустить (для комментария)"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data=BookingAction(action="skip").pack())
    )
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="❌ Отменить запись", callback_data=BookingAction(action="cancel").pack())
    )
    return builder.as_markup()


def get_masseur_action_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    """Кнопки для массажиста: Подтвердить или Редактировать запись"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="✅ Подтвердить запись",
            callback_data=MasseurAction(action="confirm", record_id=booking_id).pack()
        )
    )
    builder.add(
        InlineKeyboardButton(
            text="✏️ Редактировать запись",
            callback_data=MasseurAction(action="edit", record_id=booking_id).pack()
        )
    )
    builder.adjust(1)
    return builder.as_markup()


def get_masseur_edit_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    """Кнопки для выбора что редактировать (для массажиста)"""
    builder = InlineKeyboardBuilder()

    fields = [
        ("👤 Имя родителя", "parent_name"),
        ("👶 Имя ребенка", "child_name"),
        ("🎂 Возраст ребенка", "child_age"),
        ("💆 Вид массажа", "massage_type"),
        ("📅 Дата и время", "date_time"),
        ("💬 Комментарий", "comment"),
        ("✅ Завершить редактирование", "done"),
    ]

    for text, field in fields:
        builder.add(
            InlineKeyboardButton(
                text=text,
                callback_data=MasseurEditField(field=field, record_id=booking_id).pack()
            )
    )

    builder.adjust(1)
    return builder.as_markup()