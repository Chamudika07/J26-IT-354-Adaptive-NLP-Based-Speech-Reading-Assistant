"""Bounded page-wise PDFium renderer for validated synthetic research PDFs."""

from pathlib import Path

import pypdfium2 as pdfium

from preprocessing.recipes import pixel_digest
from rasterizers.base import ALLOWED_DPI, VERSION


def render(path: Path, dpi: int = 300):
    if dpi not in ALLOWED_DPI:
        raise ValueError("undeclared DPI")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("resource_limit_exceeded")
    # Caller must obtain successful Phase 2A validation; this renderer is not PDF validation.
    document = pdfium.PdfDocument(path)
    try:
        if not 1 <= len(document) <= 25:
            raise ValueError("page_limit_exceeded")
        for index in range(len(document)):
            page = document[index]
            bitmap = None
            try:
                width, height = page.get_size()
                import math

                w, h = math.ceil(width * dpi / 72), math.ceil(height * dpi / 72)
                if min(w, h) < 1 or max(w, h) > 6000 or w * h > 12_000_000:
                    raise ValueError("resource_limit_exceeded")
                bitmap = page.render(scale=dpi / 72)
                image = bitmap.to_pil().convert("RGB")
                yield (
                    image,
                    {
                        "page_number": index + 1,
                        "page_size_points": [width, height],
                        "dpi": dpi,
                        "scale": dpi / 72,
                        "version": VERSION,
                        "pypdfium2": str(pdfium.PYPDFIUM_INFO),
                        "pdfium": str(pdfium.PDFIUM_INFO),
                        "render_pixel_digest": pixel_digest(image),
                    },
                )
            finally:
                if bitmap is not None:
                    bitmap.close()
                page.close()
    finally:
        document.close()
