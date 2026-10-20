"""Untrusted PDF parsing. Called only inside the isolated extractor process."""

import io
from typing import Any

from pypdf import PdfReader
from pypdf.generic import ArrayObject, ContentStream, DictionaryObject, IndirectObject, StreamObject

from app.modules.reading_materials.normalization import validate_text
from app.modules.reading_materials.pdf.contracts import (
    MAX_BYTES,
    MAX_PAGES,
    MAX_TEXT,
    REJECT_ACTIONS,
    REJECT_KEYS,
    ExtractionResult,
    PageEvidence,
    failed,
)
from app.modules.reading_materials.segmentation import words


class Rejected(Exception):
    pass


def inspect_graph(root: Any) -> None:
    stack = [(root, 0)]
    seen: set[tuple[int, int] | int] = set()
    count = 0
    while stack:
        obj, depth = stack.pop()
        count += 1
        if count > 10000 or depth > 32:
            raise Rejected("resource_limit_exceeded")
        if isinstance(obj, IndirectObject):
            identity: tuple[int, int] | int = (obj.idnum, obj.generation)
            if identity in seen:
                continue
            seen.add(identity)
            obj = obj.get_object()
        if isinstance(obj, DictionaryObject):
            if any(key in obj for key in REJECT_KEYS) or obj.get("/S") in REJECT_ACTIONS:
                raise Rejected("unsupported_pdf_features")
            if isinstance(obj, StreamObject) and any(
                k in obj for k in ("/F", "/FFilter", "/FDecodeParms")
            ):
                raise Rejected("unsupported_pdf_features")
            if id(obj) in seen:
                continue
            seen.add(id(obj))
            # Never ingest document metadata or follow parent backlinks.
            stack.extend(
                (v, depth + 1) for k, v in obj.items() if k not in ("/Parent", "/Metadata")
            )
        elif isinstance(obj, ArrayObject):
            stack.extend((v, depth + 1) for v in obj)


def content_warnings(page: Any, reader: PdfReader) -> set[str]:
    warnings: set[str] = set()
    budget = [0]
    seen: set[int] = set()

    def visit(stream: Any, resources: Any, depth: int) -> None:
        if depth > 16:
            warnings.add("inspection_uncertain")
            return
        if stream is None:
            return
        content = ContentStream(stream, reader)
        for operands, operator in content.operations:
            budget[0] += 1
            if budget[0] > 100000:
                raise Rejected("resource_limit_exceeded")
            if operator == b"INLINE IMAGE":
                warnings.add("painted_image")
            elif operator == b"Do":
                try:
                    obj = resources["/XObject"][operands[0]].get_object()
                    kind = obj.get("/Subtype")
                    if kind == "/Image":
                        warnings.add("painted_image")
                    elif kind == "/Form":
                        if id(obj) in seen:
                            warnings.add("inspection_uncertain")
                        else:
                            seen.add(id(obj))
                            visit(obj, obj.get("/Resources", resources), depth + 1)
                    else:
                        warnings.add("inspection_uncertain")
                except Rejected:
                    raise
                except Exception:
                    warnings.add("inspection_uncertain")
            elif operator in (b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*", b"sh"):
                warnings.add("vector_content")

    visit(page.get("/Contents"), page.get("/Resources", {}), 0)
    if page.get("/Annots") or page.get("/OC"):
        warnings.add("inspection_uncertain")
    return warnings


def extract(data: bytes) -> ExtractionResult:
    try:
        if not data.startswith(b"%PDF-") or len(data) > MAX_BYTES:
            return failed("malformed_pdf")
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            return failed("encrypted_pdf")
        count = len(reader.pages)
        if not 1 <= count <= MAX_PAGES:
            return failed("page_limit_exceeded")
        inspect_graph(reader.trailer["/Root"])
        texts: list[str] = []
        pages: list[PageEvidence] = []
        offset = 0
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text(
                orientations=(0, 90, 180, 270), space_width=200, extraction_mode="plain"
            )
            if offset + len(text) > MAX_TEXT:
                return failed("text_limit_exceeded")
            warnings = content_warnings(page, reader)
            if "\ufffd" in text:
                warnings.add("replacement_character")
            word_count = len(words(text))
            pages.append(
                PageEvidence(
                    page_number=number,
                    text_start=offset,
                    text_end=offset + len(text),
                    raw_character_count=len(text),
                    lexical_word_count=word_count,
                    text_status="lexical" if word_count else ("nonlexical" if text else "empty"),
                    warning_codes=sorted(warnings),  # type: ignore[arg-type]
                )
            )
            texts.append(text)
            offset += len(text) + 2
        assembled = "\n\n".join(texts)
        # Empty evidence is permitted, unsupported characters are not.
        try:
            validate_text(assembled if assembled.strip() else assembled + "a")
        except ValueError:
            return failed("unsupported_extracted_text")
        if any("painted_image" in p.warning_codes and not p.lexical_word_count for p in pages):
            status, code = "ocr_required", "image_without_text"
        elif any(p.warning_codes for p in pages):
            status, code = "needs_review", "ambiguous_content"
        elif not any(p.lexical_word_count for p in pages):
            return failed("no_usable_text")
        else:
            status, code = "extracted", None
        return ExtractionResult(
            status=status,  # type: ignore[arg-type]
            outcome_code=code,
            assembled_text=assembled,
            pages=pages,
        )
    except Rejected as exc:
        return failed(str(exc))
    except MemoryError:
        return failed("resource_limit_exceeded")
    except Exception:
        return failed("malformed_pdf")
