from enum import Enum

import pymorphy3
from pytrovich.enums import Case
from pytrovich.enums import Gender as PytrovichGender
from pytrovich.enums import NamePart
from pytrovich.maker import PetrovichDeclinationMaker

from .llm_declension import decline_job_title_llm


class Gender(str, Enum):
    M = "M"
    F = "F"


_morph = pymorphy3.MorphAnalyzer()
_maker = PetrovichDeclinationMaker()


def _is_uppercase(text: str) -> bool:
    return text == text.upper() and text != text.lower()


def _apply_case(text: str, is_upper: bool) -> str:
    if is_upper:
        return text.upper()
    return text


def detect_gender(firstname: str, patronymic: str) -> Gender:
    if not patronymic:
        if not firstname:
            return Gender.M
        parsed = _morph.parse(firstname)[0]
        if "femn" in parsed.tag:
            return Gender.F
        return Gender.M

    patronymic_lower = patronymic.lower()
    if patronymic_lower.endswith("ич") or patronymic_lower.endswith("ьич"):
        return Gender.M
    if patronymic_lower.endswith("на"):
        return Gender.F

    parsed = _morph.parse(patronymic)[0]
    if "femn" in parsed.tag:
        return Gender.F
    return Gender.M


def decline_fio(surname: str, firstname: str, patronymic: str, gender: Gender) -> str:
    pytrovich_gender = PytrovichGender.MALE if gender == Gender.M else PytrovichGender.FEMALE

    is_upper = _is_uppercase(surname) if surname else False

    declined_parts = []

    if surname:
        s_title = surname.title() if is_upper else surname
        declined = _maker.make(NamePart.LASTNAME, pytrovich_gender, Case.DATIVE, s_title)
        declined_parts.append(_apply_case(declined, is_upper))

    if firstname:
        f_title = firstname.title() if is_upper else firstname
        declined = _maker.make(NamePart.FIRSTNAME, pytrovich_gender, Case.DATIVE, f_title)
        declined_parts.append(_apply_case(declined, is_upper))

    if patronymic:
        p_title = patronymic.title() if is_upper else patronymic
        declined = _maker.make(NamePart.MIDDLENAME, pytrovich_gender, Case.DATIVE, p_title)
        declined_parts.append(_apply_case(declined, is_upper))

    return " ".join(declined_parts)


def decline_position(position: str) -> str:
    if not position:
        return ""

    is_upper = _is_uppercase(position)
    result = decline_job_title_llm(position.title() if is_upper else position)
    return _apply_case(result, is_upper)


def get_greeting(gender: Gender) -> str:
    return "УВАЖАЕМЫЙ" if gender == Gender.M else "УВАЖАЕМАЯ"


def get_name_for_greeting(firstname: str, patronymic: str) -> str:
    is_upper = _is_uppercase(firstname) if firstname else False
    parts = [p for p in [firstname, patronymic] if p]
    result = " ".join(parts)
    return _apply_case(result, is_upper)