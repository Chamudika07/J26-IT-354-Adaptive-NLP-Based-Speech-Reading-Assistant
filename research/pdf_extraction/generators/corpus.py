"""Two disjoint authoring systems: dev field notes and held-out museum cards."""

import io
import json
import random
import re
from importlib.metadata import version
from pathlib import Path

import reportlab
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from schemas import CATEGORIES, Manifest, digest

GENERATOR_VERSION = "original-source-v1"
FONT = Path(reportlab.__file__).parent / "fonts/Vera.ttf"


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def author(category, split, index, seed):
    rng = random.Random(seed)
    held = split == "heldout"
    # Different genres, geometry, page size and block construction across splits.
    noun = rng.choice(["cedar", "otter", "harbor", "copper", "fern", "comet"])
    body = (
        f"Visitors compare {noun} exhibits before sketching their observations."
        if held
        else f"Our field team measured the {noun} beside a quiet path."
    )
    title = f"Gallery card {index + 1}" if held else f"Field note {index + 1}"
    lines = [title, body, ("Record 42: retain each detail." if held else "We counted 17 samples.")]
    if category == "unicode":
        lines = (
            [title, "Résumé: piñata à la carte; Ö costs €8.", "Résumé display: Ångström."]
            if held
            else [title, "Café naïve coöperate — £12; Ω and Æ.", "Café: accented letter."]
        )
    if category == "punctuation_hyphenation":
        lines = [
            title,
            "Isn't exhibit #7 well-lit? Yes: 3.75."
            if held
            else "Don't re-label 12.5 items; ‘keep’ punctuation!",
            "archaeo-" if held else "inter-",
            "logical record." if held else "national study.",
        ]
    if category == "headings_paragraphs":
        lines = [title.upper(), "Observation", body, "Conclusion", "Compare, then explain."]
    if category == "tables":
        lines = (
            [title, "Mineral", "Mass", "Quartz", "41", "Basalt", "76"]
            if held
            else [title, "Item", "Count", "Amber", "23", "Indigo", "58"]
        )
    if category == "two_column":
        lines = [
            title,
            "LEFTSTART",
            "Artifact labels guide visitors." if held else "Field samples guide our notes.",
            "LEFTEND",
            "RIGHTSTART",
            "Compare these artifacts in sequence."
            if held
            else "A second column explains the arrangement.",
            "RIGHTEND",
        ]
    count = (3 if held else 2) if category in {"multipage", "headers_footers_page_numbers"} else 1
    pages = []
    for p in range(count):
        texts = list(lines)
        if count > 1:
            texts.insert(0, f"PAGEID{p + 1}")
        if category == "headers_footers_page_numbers":
            texts = [
                "Museum bulletin" if held else "Expedition bulletin",
                *texts,
                f"Page {p + 1} of {count}",
            ]
        blocks = []
        for j, text in enumerate(texts):
            x, y = (54 if held else 36), (720 if held else 760) - j * (29 if held else 20)
            if category == "two_column" and j >= 4:
                x, y = 320, (691 if held else 740) - (j - 4) * (29 if held else 20)
            if category == "tables" and j:
                x = 54 + ((j - 1) % 2) * 200
                y = 670 - ((j - 1) // 2) * 35
            blocks.append({"id": f"p{p + 1}b{j}", "text": text, "x": x, "y": y})
        # Held-out columns intentionally authored right column first in content stream.
        draw_order = list(range(len(blocks)))
        if held and category == "two_column":
            draw_order = [0, 4, 5, 6, 1, 2, 3]
        pages.append(
            {
                "id": f"PAGEID{p + 1}" if count > 1 else texts[0],
                "blocks": blocks,
                "draw_order": draw_order,
                "image_text": None,
            }
        )
    policy, code, assessment = "extracted", None, "complete"
    if category == "two_column" and held:
        assessment = "ordering_problem"
    if category == "mixed_text_images":
        pages[0]["image_text"] = "" if index % 2 == 0 else "The hidden map names three islands."
        assessment = "complete" if index % 2 == 0 else "missing_visible_content"
        policy, code = "needs_review", "ambiguous_content"
    if category == "image_only_or_scanned_like":
        pages[0]["blocks"] = []
        pages[0]["draw_order"] = []
        pages[0]["image_text"] = (
            f"Museum raster card {index + 1}: pottery preserves patterns from {noun}."
            if held
            else f"Field raster lesson {index + 1}: {noun} grows near sunlight."
        )
        if index == 1:
            pages.insert(
                0,
                {
                    "id": "PAGEIDTEXT",
                    "blocks": [
                        {"id": "intro", "text": "PAGEIDTEXT", "x": 54, "y": 720},
                        {"id": "body", "text": body, "x": 54, "y": 690},
                    ],
                    "draw_order": [0, 1],
                    "image_text": None,
                },
            )
        assessment = "missing_visible_content"
        policy, code = "ocr_required", "image_without_text"
        if held and index == 3:
            pages[0]["blocks"] = [{"id": "caption", "text": "Small caption", "x": 54, "y": 720}]
            pages[0]["draw_order"] = [0]
            pages[0]["id"] = "Small caption"
            policy, code = "needs_review", "ambiguous_content"
    mode = None
    if category == "invalid_or_unsupported":
        mode = (
            ["blank", "encrypted"] if not held else ["malformed", "attachment", "form", "action"]
        )[index]
        policy, assessment = "failed", "unusable"
        code = {
            "blank": "no_usable_text",
            "encrypted": "encrypted_pdf",
            "malformed": "malformed_pdf",
        }.get(mode, "unsupported_pdf_features")
        if mode in {"blank", "malformed"}:
            pages = (
                []
                if mode == "malformed"
                else [{"id": "blank", "blocks": [], "draw_order": [], "image_text": None}]
            )
    return {
        "category": category,
        "split": split,
        "pages": pages,
        "mode": mode,
        "page_size": [612, 792] if held else [595, 842],
        "font_size": 11 if held else 10,
        "expected_policy_outcome": policy,
        "expected_outcome_code": code,
        "content_assessment": assessment,
    }


def render(source, path):
    if source["mode"] == "malformed":
        path.write_bytes(b"%PDF-1.7\nOriginal incomplete synthetic file\n")
        return
    if "BenchmarkVera" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("BenchmarkVera", str(FONT)))
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=source["page_size"], invariant=1, pageCompression=0)
    for page in source["pages"]:
        canvas.setFont("BenchmarkVera", source["font_size"])
        for i in page["draw_order"]:
            block = page["blocks"][i]
            font = pdfmetrics.getFont("BenchmarkVera")
            if any(ord(c) not in font.face.charToGlyph for c in block["text"]):
                raise ValueError("authoring font cannot render a reference character")
            width = pdfmetrics.stringWidth(block["text"], "BenchmarkVera", source["font_size"])
            if (
                block["x"] + width > source["page_size"][0]
                or not 0 < block["y"] < source["page_size"][1]
            ):
                raise ValueError("authored text extends beyond page")
            canvas.drawString(block["x"], block["y"], block["text"])
        if page["image_text"] is not None:
            raster = Image.new("RGB", (480, 100), "white")
            ImageDraw.Draw(raster).text((8, 25), page["image_text"] or "LOGO", fill="black")
            canvas.drawImage(ImageReader(raster), 50, 400, width=480, height=100)
        canvas.showPage()
    canvas.save()
    data = buffer.getvalue()
    if source["mode"] in {"encrypted", "attachment", "form", "action"}:
        from pypdf.generic import DictionaryObject, NameObject

        writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
        if source["mode"] == "encrypted":
            writer.encrypt("synthetic-password")
        elif source["mode"] == "attachment":
            writer.add_attachment("original.txt", b"Benign original attachment")
        elif source["mode"] == "action":
            writer._root_object[NameObject("/OpenAction")] = DictionaryObject()
        else:
            writer._root_object[NameObject("/AcroForm")] = DictionaryObject()
        out = io.BytesIO()
        writer.write(out)
        data = out.getvalue()
    path.write_bytes(data)


def generate(root, split, production_commit, existing=None):
    root.mkdir(parents=True, exist_ok=True)
    entries = list(existing.fixture_entries) if existing else []
    if any(f.split == split for f in entries):
        raise ValueError("split already generated; frozen fixtures must not be overwritten")
    for category in CATEGORIES:
        for i in range(4 if split == "heldout" else 2):
            fid = f"{split}-{category}-{i + 1:02}"
            directory = root / fid
            directory.mkdir(exist_ok=False)
            seed = (
                22081766
                + CATEGORIES.index(category) * 100
                + i
                + (10000 if split == "heldout" else 0)
            )
            source = author(category, split, i, seed)
            write_json(directory / "source.json", source)
            render(source, directory / "document.pdf")
            pages = ["".join(b["text"] + "\n" for b in p["blocks"]) for p in source["pages"]]
            for p, text in enumerate(pages):
                (directory / f"page-{p + 1}.txt").write_text(text)
            assembled = "\n\n".join(pages)
            (directory / "assembled.txt").write_text(assembled)
            (directory / "visible.txt").write_text(
                "\n\n".join(
                    text + (page["image_text"] or "")
                    for text, page in zip(pages, source["pages"], strict=True)
                )
            )
            anchors = [b["text"] for p in source["pages"] for b in p["blocks"]]
            unique = [a for a in anchors if anchors.count(a) == 1]
            offsets, start = [], 0
            for page in pages:
                offsets.append([start, start + len(page)])
                start += len(page) + 2
            write_json(
                directory / "structure.json",
                {
                    "page_ids": [p["id"] for p in source["pages"]],
                    "page_id_testable": bool(pages) and all(p["blocks"] for p in source["pages"]),
                    "precedence_pairs": list(zip(unique, unique[1:], strict=False)),
                    "offsets": offsets,
                    "block_ids": [[b["id"] for b in p["blocks"]] for p in source["pages"]],
                    "tokens": re.findall(r"\S+", assembled),
                    "token_policy": "maximal-nonwhitespace",
                    "table_rows": (
                        [["Mineral", "Mass"], ["Quartz", "41"], ["Basalt", "76"]]
                        if split == "heldout"
                        else [["Item", "Count"], ["Amber", "23"], ["Indigo", "58"]]
                    )
                    if category == "tables"
                    else [],
                    "rationale": "Logical authoring-source order; raw line terminators are LF.",
                    "visible_ground_truth": {
                        "reference": f"{fid}/visible.txt",
                        "sha256": digest(directory / "visible.txt"),
                    },
                },
            )

            def artifact(name, fid=fid, directory=directory):
                return {"reference": f"{fid}/{name}", "sha256": digest(directory / name)}

            entries.append(
                {
                    "fixture_id": fid,
                    "primary_category": category,
                    "feature_tags": [category],
                    "split": split,
                    "template_family_id": f"{split}-{category}",
                    "provenance_type": "original",
                    "creator_or_source_reference": "Phase 2B original synthetic generator",
                    "license_or_permission_reference": (
                        "Original text: CC0-1.0; font: Bitstream Vera license"
                    ),
                    "generator_name": "ReportLab",
                    "generator_version": version("reportlab"),
                    "generator_configuration": {
                        "implementation": GENERATOR_VERSION,
                        "invariant": True,
                        "font": "Bitstream Vera",
                        "font_sha256": digest(FONT),
                        "font_license": "ReportLab fonts/bitstream-vera-license.txt",
                        "pypdf_version": version("pypdf"),
                        "pillow_version": version("pillow"),
                    },
                    "generator_seed": seed,
                    "source_artifact_reference": f"{fid}/document.pdf",
                    "source_sha256": digest(directory / "document.pdf"),
                    "source_byte_count": (directory / "document.pdf").stat().st_size,
                    "expected_page_count": None if source["mode"] == "malformed" else len(pages),
                    "expected_policy_outcome": source["expected_policy_outcome"],
                    "expected_outcome_code": source["expected_outcome_code"],
                    "content_assessment": source["content_assessment"],
                    "reference_scope": "embedded_only"
                    if any(p["image_text"] for p in source["pages"])
                    else "embedded_and_visible",
                    "page_ground_truth": [artifact(f"page-{p + 1}.txt") for p in range(len(pages))],
                    "assembled_ground_truth": artifact("assembled.txt"),
                    "structural_annotation": artifact("structure.json"),
                    "authoring_source": artifact("source.json"),
                    "exact_match_required": category == "simple_single_column",
                    "metric_eligibility": category != "invalid_or_unsupported",
                    "known_limitations": [
                        "One generator engine; exploratory synthetic corpus",
                        "Automated authoring-source annotations, no independent human raters",
                    ],
                    "notes": "Embedded primary; visible raster reference separate; no OCR.",
                }
            )
    return Manifest(production_commit=production_commit, fixture_entries=entries)
