import hashlib
import tempfile

import pytest

from app.modules.reading_materials.pdf import contracts, runner, service
from app.modules.reading_materials.pdf.extractor import extract

from .conftest import pdf_bytes


@pytest.mark.parametrize(
    "texts,image,vector,status,code",
    [
        (("A cat rests.",), False, False, "extracted", None),
        (("Café — a bird!",), False, False, "extracted", None),
        (("A cat.", "", "A dog."), False, False, "extracted", None),
        (("",), False, False, "failed", "no_usable_text"),
        (("1234",), False, False, "failed", "no_usable_text"),
        (("",), True, False, "ocr_required", "image_without_text"),
        (("A cat.",), True, False, "needs_review", "ambiguous_content"),
        (("A cat.",), False, True, "needs_review", "ambiguous_content"),
        (("",), False, True, "needs_review", "ambiguous_content"),
    ],
)
def test_quality(texts, image, vector, status, code):
    result = extract(pdf_bytes(texts, image=image, vector=vector))
    assert (result.status, result.outcome_code) == (status, code)
    service.validate_result(result)


@pytest.mark.parametrize("feature", ["javascript", "attachment", "form", "action"])
def test_active_features(feature):
    assert extract(pdf_bytes(feature=feature)).outcome_code == "unsupported_pdf_features"


@pytest.mark.parametrize(
    "data,code",
    [
        (b"%PDF-broken", "malformed_pdf"),
        (b"not a PDF", "malformed_pdf"),
        (pdf_bytes(encrypted=True), "encrypted_pdf"),
        (pdf_bytes(()), "page_limit_exceeded"),
        (pdf_bytes(("A cat.",) * 26), "page_limit_exceeded"),
        (pdf_bytes(("a " * 25001,)), "text_limit_exceeded"),
    ],
)
def test_rejections(data, code):
    result = extract(data)
    assert result.outcome_code == code
    assert result.assembled_text is None and result.pages == []


def test_assembly_empty_offsets_and_no_rewrite():
    texts = ("Café—first column; second column. well-", "", "being? A table: a b c.")
    result = extract(pdf_bytes(texts))
    assert result.status == "extracted"
    assert result.assembled_text == "\n\n".join(texts)
    assert result.pages[1].text_start == result.pages[1].text_end
    for p, t in zip(result.pages, texts, strict=True):
        assert result.assembled_text[p.text_start : p.text_end] == t
    assert extract(pdf_bytes(texts)).model_dump() == result.model_dump()


def test_child_boundary():
    data = pdf_bytes()
    with tempfile.TemporaryFile() as stream:
        stream.write(data)
        stream.seek(0)
        result = runner.run(stream, hashlib.sha256(data).hexdigest(), len(data))
    assert result.status == "extracted"
    service.validate_result(result)


def test_digest_mismatch():
    data = pdf_bytes()
    with tempfile.TemporaryFile() as stream:
        stream.write(data)
        stream.seek(0)
        assert runner.run(stream, "0" * 64, len(data)).outcome_code == "integrity_failed"


def test_manifest(monkeypatch):
    original = contracts.fingerprint()
    assert len(original) == 64 and original == contracts.fingerprint()
    monkeypatch.setattr(contracts, "MAX_PAGES", 24)
    assert contracts.fingerprint() != original


def test_timeout_kills_and_reaps(monkeypatch):
    import subprocess

    class Child:
        returncode = 0
        killed = False

        def wait(self, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired("sanitized", timeout)

        def kill(self):
            self.killed = True

    child = Child()
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: child)
    data = b"%PDF-"
    with tempfile.TemporaryFile() as stream:
        stream.write(data)
        stream.seek(0)
        result = runner.run(stream, hashlib.sha256(data).hexdigest(), len(data))
    assert child.killed and result.outcome_code == "resource_limit_exceeded"


@pytest.mark.parametrize(
    "fault", ["offset", "count", "ordinal", "missing", "text", "accepted_warning"]
)
def test_reject_untrusted_child_evidence(fault):
    result = extract(pdf_bytes())
    if fault == "offset":
        result.pages[0].text_start = 1
    elif fault == "count":
        result.pages[0].lexical_word_count += 1
    elif fault == "ordinal":
        result.pages[0].page_number = 2
    elif fault == "missing":
        result.pages = []
    elif fault == "text":
        result.assembled_text = None
    else:
        result.pages[0].warning_codes = ["inspection_uncertain"]
    with pytest.raises(ValueError):
        service.validate_result(result)


def test_unused_image_does_not_trigger_ocr():
    import io

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    reader = PdfReader(io.BytesIO(pdf_bytes(image=True)))
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    page = writer.pages[0]
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 200 Td (A cat.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    assert extract(out.getvalue()).status == "extracted"


def test_line_break_hyphenation_not_joined():
    import io

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(pdf_bytes())).pages[0])
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 200 Td (well-) Tj 0 -20 Td (being.) Tj ET")
    writer.pages[0][NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    result = extract(out.getvalue())
    assert result.assembled_text == "well-\nbeing."


def test_nested_form_painted_image():
    import io

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (
        ArrayObject,
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
        NumberObject,
    )

    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(pdf_bytes(("",), image=True))).pages[0])
    page = writer.pages[0]
    form = DecodedStreamObject()
    form.set_data(b"/Im1 Do")
    form.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/BBox"): ArrayObject([NumberObject(n) for n in (0, 0, 100, 100)]),
            NameObject("/Resources"): page["/Resources"],
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/Form1"): writer._add_object(form)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"/Form1 Do")
    page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    assert extract(out.getvalue()).status == "ocr_required"


def test_external_stream_is_rejected():
    import io

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, TextStringObject

    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(pdf_bytes())).pages[0])
    writer.pages[0]["/Contents"][NameObject("/F")] = TextStringObject(
        "https://invalid.example/private"
    )
    out = io.BytesIO()
    writer.write(out)
    assert extract(out.getvalue()).outcome_code == "unsupported_pdf_features"


def test_child_drops_credentials_and_suppresses_output(monkeypatch, caplog):
    import subprocess

    captured = {}

    class Child:
        returncode = 0

        def wait(self, timeout=None):
            pass

    def spawn(args, **kwargs):
        captured.update(kwargs)
        kwargs["stdout"].write(b"PRIVATE PARSER OUTPUT")
        return Child()

    monkeypatch.setattr(runner.subprocess, "Popen", spawn)
    monkeypatch.setenv("DATABASE_URL", "private-credential")
    data = pdf_bytes()
    with tempfile.TemporaryFile() as stream:
        stream.write(data)
        stream.seek(0)
        result = runner.run(stream, hashlib.sha256(data).hexdigest(), len(data))
    assert captured["env"] == {} and captured["stderr"] == subprocess.DEVNULL
    assert result.outcome_code == "backend_failed"
    assert "PRIVATE PARSER OUTPUT" not in caplog.text + result.model_dump_json()


@pytest.mark.parametrize(
    "value,status",
    [
        ("Cafe\u0301. A cat!", "extracted"),
        ("A \U0001f642 bird.", "extracted"),
        ("A \ufffd bird.", "needs_review"),
    ],
)
def test_unicode_cmap_exact_codepoints(value, status):
    import io

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(pdf_bytes())).pages[0])
    page = writer.pages[0]
    characters = list(dict.fromkeys(value))
    mapping = "\n".join(
        f"<{i:02x}> <{c.encode('utf-16-be').hex()}>" for i, c in enumerate(characters, 1)
    )
    cmap = DecodedStreamObject()
    cmap.set_data(
        (
            "begincmap\n/CMapType 2 def\n1 begincodespacerange\n<00> <ff>\nendcodespacerange\n"
            + str(len(characters))
            + " beginbfchar\n"
            + mapping
            + "\nendbfchar\nendcmap"
        ).encode()
    )
    page["/Resources"]["/Font"]["/F1"][NameObject("/ToUnicode")] = writer._add_object(cmap)
    encoded = bytes(characters.index(c) + 1 for c in value).hex().encode()
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 200 Td <" + encoded + b"> Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    result = extract(out.getvalue())
    assert result.status == status
    assert result.assembled_text == value
    assert result.pages[0].text_end == len(value)
