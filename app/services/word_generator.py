import re
from pathlib import Path

from docx import Document
from docx.text.paragraph import Paragraph
from docx.text.run import Run


PLACEHOLDER_MAP = {
    "{{адрес}}": "address",
    "{{организация}}": "organization",
    "{{должность_дат}}": "position_dative",
    "{{фио_дат}}": "fullname_dative",
    "{{имя_отчество}}": "name_for_greeting",
    "{{уважаемый}}": "greeting",
}

REQUIRED_PLACEHOLDERS = set(PLACEHOLDER_MAP.keys())


def _replace_in_run_ci(run: Run, placeholder_lower: str, value: str) -> bool:
    run_text_lower = run.text.lower()
    if placeholder_lower not in run_text_lower:
        return False
    
    pattern = re.escape(placeholder_lower)
    match = re.search(pattern, run_text_lower)
    if not match:
        return False
    
    actual_placeholder = run.text[match.start():match.end()]
    run.text = run.text.replace(actual_placeholder, value.upper())
    
    return True


def _replace_in_paragraph_ci(paragraph: Paragraph, replacements: dict[str, str]) -> None:
    if not paragraph.text:
        return
    
    text_lower = paragraph.text.lower()
    
    for placeholder_lower, value in replacements.items():
        if placeholder_lower in text_lower:
            for run in paragraph.runs:
                _replace_in_run_ci(run, placeholder_lower, value)


def _replace_in_table(table, replacements: dict[str, str]) -> None:
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                _replace_in_paragraph_ci(paragraph, replacements)


def generate_telegram(
    template_path: str,
    data: dict,
    output_path: str,
) -> str:
    template = Path(template_path)
    if not template.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    doc = Document(template_path)

    replacements = {p: data.get(k, "") for p, k in PLACEHOLDER_MAP.items()}

    for paragraph in doc.paragraphs:
        _replace_in_paragraph_ci(paragraph, replacements)

    for table in doc.tables:
        _replace_in_table(table, replacements)

    for section in doc.sections:
        for header in [section.header, section.footer]:
            for paragraph in header.paragraphs:
                _replace_in_paragraph_ci(paragraph, replacements)
            for table in header.tables:
                _replace_in_table(table, replacements)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)

    return str(output.absolute())


def validate_template(template_path: str) -> list[str]:
    template = Path(template_path)
    if not template.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    doc = Document(template_path)

    all_text = ""
    for paragraph in doc.paragraphs:
        all_text += paragraph.text + " "

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    all_text += paragraph.text + " "

    for section in doc.sections:
        for header in [section.header, section.footer]:
            for paragraph in header.paragraphs:
                all_text += paragraph.text + " "

    pattern = r"\{\{[^}]+\}\}"
    found_placeholders = re.findall(pattern, all_text)
    
    found_set = {p.lower() for p in found_placeholders}
    
    missing = REQUIRED_PLACEHOLDERS - found_set
    unknown = found_set - REQUIRED_PLACEHOLDERS

    errors = []
    if missing:
        errors.append(f"В шаблоне не найдены метки: {', '.join(sorted(missing))}")
    if unknown:
        errors.append(f"Неизвестные метки в шаблоне: {', '.join(sorted(unknown))}")

    return errors
