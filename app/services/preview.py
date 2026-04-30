import shutil
import subprocess
from pathlib import Path


def generate_preview(docx_path: str, output_dir: str) -> str:
    docx = Path(docx_path)
    if not docx.exists():
        raise FileNotFoundError(f"DOCX file not found: {docx_path}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    libreoffice_cmd = shutil.which("libreoffice") or shutil.which("soffice")
    if not libreoffice_cmd:
        raise RuntimeError(
            "LibreOffice not found. Please install LibreOffice to enable preview generation."
        )

    result = subprocess.run(
        [
            libreoffice_cmd,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(docx),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")

    pdf_path = out_dir / f"{docx.stem}.pdf"
    if not pdf_path.exists():
        raise RuntimeError(f"PDF file was not created: {pdf_path}")

    pdftoppm_cmd = shutil.which("pdftoppm")
    if pdftoppm_cmd:
        png_path = out_dir / f"{docx.stem}.png"
        result = subprocess.run(
            [
                pdftoppm_cmd,
                "-png",
                "-singlefile",
                str(pdf_path),
                str(out_dir / docx.stem),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and png_path.exists():
            pdf_path.unlink()
            return str(png_path.absolute())

    try:
        from pdf2image import convert_from_path

        images = convert_from_path(str(pdf_path), first_page=1, last_page=1)
        if images:
            png_path = out_dir / f"{docx.stem}.png"
            images[0].save(png_path, "PNG")
            pdf_path.unlink()
            return str(png_path.absolute())
    except ImportError:
        pass

    raise RuntimeError(
        "Could not convert PDF to PNG. Install poppler-utils (pdftoppm) or pdf2image package."
    )
