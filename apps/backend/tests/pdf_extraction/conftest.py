"""Only synthetic original PDF data; no external corpus or learner files."""

import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)

from tests.reading_materials.conftest import setup_material  # noqa: F401
from tests.reading_materials.test_concurrency import context  # noqa: F401


def pdf_bytes(
    texts=("A cat rests. A dog runs!",), *, image=False, vector=False, encrypted=False, feature=None
):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
        resources = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        page[NameObject("/Resources")] = resources
        content = b""
        if text:
            encoded = text.encode("cp1252").hex().encode()
            content += b"BT /F1 12 Tf 20 200 Td <" + encoded + b"> Tj ET\n"
        if image:
            raster = DecodedStreamObject()
            raster.set_data(b"\x00")
            raster.update(
                {
                    NameObject("/Type"): NameObject("/XObject"),
                    NameObject("/Subtype"): NameObject("/Image"),
                    NameObject("/Width"): NumberObject(1),
                    NameObject("/Height"): NumberObject(1),
                    NameObject("/ColorSpace"): NameObject("/DeviceGray"),
                    NameObject("/BitsPerComponent"): NumberObject(8),
                }
            )
            resources[NameObject("/XObject")] = DictionaryObject(
                {NameObject("/Im1"): writer._add_object(raster)}
            )
            content += b"q 100 0 0 100 0 0 cm /Im1 Do Q\n"
        if vector:
            content += b"0 0 10 10 re f\n"
        stream = DecodedStreamObject()
        stream.set_data(content)
        page[NameObject("/Contents")] = writer._add_object(stream)
    if feature == "javascript":
        writer._root_object[NameObject("/JavaScript")] = DictionaryObject()
    elif feature == "attachment":
        writer.add_attachment("synthetic.txt", b"original test")
    elif feature == "form":
        writer._root_object[NameObject("/AcroForm")] = DictionaryObject(
            {NameObject("/Fields"): ArrayObject()}
        )
    elif feature == "action":
        writer._root_object[NameObject("/OpenAction")] = DictionaryObject(
            {NameObject("/S"): NameObject("/Launch")}
        )
    if encrypted:
        writer.encrypt("")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.fixture
def pdf_storage(settings, tmp_path):
    settings.pdf_storage_root = tmp_path / "private-pdf"
    return settings.pdf_storage_root
