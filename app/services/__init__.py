"""Services for telegram generation."""
from app.services.declension import (
    Gender,
    decline_fio,
    decline_position,
    detect_gender,
    get_greeting,
    get_name_for_greeting,
)
from app.services.excel_parser import parse_excel
from app.services.preview import generate_preview
from app.services.word_generator import generate_telegram

__all__ = [
    "Gender",
    "decline_fio",
    "decline_position",
    "detect_gender",
    "get_greeting",
    "get_name_for_greeting",
    "parse_excel",
    "generate_preview",
    "generate_telegram",
]
