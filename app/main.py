import io
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import aiofiles
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.services import (
    Gender,
    decline_fio,
    decline_position,
    detect_gender,
    generate_preview,
    generate_telegram,
    get_greeting,
    get_name_for_greeting,
    parse_excel,
)
from app.services.word_generator import validate_template

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
WORD_TEMPLATES_DIR = BASE_DIR.parent / "word_templates"

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)

app = FastAPI(title="Telegram Generator")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _render_template(name: str, context: dict[str, Any] | None = None) -> str:
    template = env.get_template(name)
    return template.render(context or {})


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return _render_template("index.html")


@app.get("/template/excel")
async def download_excel_template() -> FileResponse:
    template_path = WORD_TEMPLATES_DIR / "template.xlsx"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Excel template not found")
    return FileResponse(
        path=template_path,
        filename="template.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/template/word")
async def download_word_template() -> FileResponse:
    template_path = WORD_TEMPLATES_DIR / "template.docx"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Word template not found")
    return FileResponse(
        path=template_path,
        filename="template.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/upload/excel")
async def upload_excel(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")

    with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        records = parse_excel(tmp_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"count": len(records), "records": records[:10], "total": len(records)}


@app.post("/upload/word")
async def upload_word(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="File must be a Word document (.docx)")

    with NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        errors = validate_template(tmp_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if errors:
        return {"valid": False, "errors": errors}

    return {"valid": True, "errors": []}


@app.post("/generate")
async def generate(
    excel_file: UploadFile = File(...),
    word_file: UploadFile = File(...),
) -> StreamingResponse:
    if not excel_file.filename or not excel_file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Excel file must be .xlsx or .xls")
    if not word_file.filename or not word_file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Word file must be .docx")

    with NamedTemporaryFile(delete=False, suffix=".xlsx") as excel_tmp:
        excel_content = await excel_file.read()
        excel_tmp.write(excel_content)
        excel_path = excel_tmp.name

    with NamedTemporaryFile(delete=False, suffix=".docx") as word_tmp:
        word_content = await word_file.read()
        word_tmp.write(word_content)
        word_path = word_tmp.name

    output_dir = Path(excel_path).parent / "output"
    output_dir.mkdir(exist_ok=True)

    try:
        records = parse_excel(excel_path)
        errors = validate_template(word_path)

        if errors:
            raise HTTPException(status_code=400, detail=f"Template errors: {', '.join(errors)}")

        generated_files = []

        for idx, record in enumerate(records):
            fullname = record.get("fullname", "")
            parts = fullname.split()
            surname = parts[0] if len(parts) > 0 else ""
            firstname = parts[1] if len(parts) > 1 else ""
            patronymic = parts[2] if len(parts) > 2 else ""

            gender = detect_gender(firstname, patronymic)
            fullname_dative = decline_fio(surname, firstname, patronymic, gender)
            position_dative = decline_position(record.get("position", ""))
            greeting = get_greeting(gender)
            name_for_greeting = get_name_for_greeting(firstname, patronymic)

            data = {
                "address": record.get("address", ""),
                "organization": record.get("organization", ""),
                "position_dative": position_dative,
                "fullname_dative": fullname_dative,
                "greeting": greeting,
                "name_for_greeting": name_for_greeting,
            }

            safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in fullname)
            output_filename = f"{idx + 1:03d}_{safe_name}.docx"
            output_path = output_dir / output_filename

            generate_telegram(word_path, data, str(output_path))
            generated_files.append(output_path)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in generated_files:
                zf.write(file_path, file_path.name)

        zip_buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(zip_buffer.read()),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=telegrams.zip"},
        )

    finally:
        Path(excel_path).unlink(missing_ok=True)
        Path(word_path).unlink(missing_ok=True)
        for f in output_dir.glob("*.docx"):
            f.unlink(missing_ok=True)


@app.post("/preview")
async def preview(
    word_file: UploadFile = File(...),
    data: str = "{}",
) -> dict[str, str]:
    import json

    if not word_file.filename or not word_file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Word file must be .docx")

    with NamedTemporaryFile(delete=False, suffix=".docx") as word_tmp:
        word_content = await word_file.read()
        word_tmp.write(word_content)
        word_path = word_tmp.name

    output_dir = Path(word_path).parent / "preview"
    output_dir.mkdir(exist_ok=True)

    try:
        try:
            preview_data = json.loads(data)
        except json.JSONDecodeError:
            preview_data = {}

        if preview_data:
            preview_docx = output_dir / "preview.docx"
            generate_telegram(word_path, preview_data, str(preview_docx))
            word_path = str(preview_docx)

        png_path = generate_preview(word_path, str(output_dir))

        return {"preview_path": png_path}

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    finally:
        Path(word_path).unlink(missing_ok=True)
