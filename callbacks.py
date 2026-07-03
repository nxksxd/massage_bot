"""
Фабрики CallbackData для типобезопасной работы с inline-кнопками.
aiogram 3.4+ поддерживает CallbackData с автоматической упаковкой/распаковкой.
"""
from aiogram.filters.callback_data import CallbackData


class BookingAction(CallbackData, prefix="bk"):
    """Действия пользователя в процессе записи."""
    action: str              # "start" | "cancel" | "confirm" | "edit" | "skip"
    record_id: int = 0       # 0 для новых записей


class EditField(CallbackData, prefix="ef"):
    """Выбор поля для редактирования (пользователь)."""
    field: str               # "parent_name" | "child_name" | "child_age" | "massage_type" | "date" | "time" | "comment"
    record_id: int = 0


class MasseurAction(CallbackData, prefix="ma"):
    """Действия массажиста над записью."""
    action: str              # "confirm" | "edit" | "done"
    record_id: int


class MasseurEditField(CallbackData, prefix="mef"):
    """Выбор поля для редактирования (массажист)."""
    field: str               # "parent_name" | "child_name" | "child_age" | "massage_type" | "date_time" | "comment"
    record_id: int