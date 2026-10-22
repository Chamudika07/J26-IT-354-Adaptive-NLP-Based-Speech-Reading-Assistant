"""Original held-out print sheets; these are never phone photographs."""

import argparse
from pathlib import Path

import reportlab
from PIL import Image, ImageDraw, ImageFont

from integrity import canonical, digest

VERSION = "ocr-phone-print-masters-heldout-v1"
PAGES = {
    "phone_camera_photo-heldout-01": (
        "Why bridges have gaps",
        [
            (
                "A bridge may look still, but its materials change slightly with temperature. "
                "On a warm day, metal expands. When the air becomes cooler, it contracts "
                "again. Engineers leave small spaces between some parts of a bridge so that "
                "these changes do not push the structure out of shape."
            ),
            (
                "These spaces are called expansion joints. You might notice a gentle bump as "
                "a vehicle crosses one. A flexible cover can protect the opening while "
                "allowing movement. The same idea appears in railway tracks and pavements. "
                "Small gaps help large structures cope with changing conditions throughout "
                "the year."
            ),
        ],
    ),
    "phone_camera_photo-heldout-02": (
        "Reading tree rings",
        [
            (
                "A tree adds a new layer of wood as it grows. In many places, the changing "
                "seasons produce a pattern of light and dark bands. Together, a pair of bands "
                "often represents one year of growth. The oldest wood lies near the centre of "
                "the trunk."
            ),
            (
                "Wide rings may suggest that conditions supported strong growth. Narrow rings "
                "can be clues to a difficult season, although several causes are possible. "
                "Scientists compare patterns from many trees before drawing conclusions. A "
                "fallen branch or a safely displayed stump can reveal these patterns without "
                "harming a living tree."
            ),
        ],
    ),
    "phone_camera_photo-heldout-03": (
        "How a periscope works",
        [
            (
                "A periscope lets someone look over an obstacle while staying below it. A "
                "simple version uses a long tube and two mirrors. One mirror sits near the "
                "top and the other near the bottom. Both mirrors are tilted so that light "
                "changes direction inside the tube."
            ),
            (
                "Light from an object enters the upper opening, reflects downwards, and then "
                "reflects towards the viewer. The mirrors guide the light along a new path. "
                "You can explore this idea with a cardboard model and safe craft mirrors. Try "
                "changing a mirror angle and observe how the view moves."
            ),
        ],
    ),
}


def wrap(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if current and font.getlength(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def generate(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    font_path = Path(reportlab.__file__).parent / "fonts/Vera.ttf"
    body_font = ImageFont.truetype(str(font_path), 31)
    heading_font = ImageFont.truetype(str(font_path), 43)
    records = []
    for fixture_id, (heading, paragraphs) in PAGES.items():
        image = Image.new("RGB", (1600, 2263), "white")
        draw = ImageDraw.Draw(image)
        blocks = []
        y = 135
        for i, text in enumerate([heading, *paragraphs]):
            font = heading_font if i == 0 else body_font
            lines = wrap(text, font, 1330)
            line_height = 64 if i == 0 else 49
            top = y
            for line in lines:
                draw.text((135, y), line, font=font, fill="black")
                y += line_height
            blocks.append(
                {
                    "id": f"b{i}",
                    "text": text,
                    "lines": lines,
                    "role": "heading" if i == 0 else "paragraph",
                    "font": "Bitstream Vera",
                    "size": 43 if i == 0 else 31,
                    "polygon": [[135, top], [1465, top], [1465, y], [135, y]],
                }
            )
            y += 65
        if y > 2100:
            raise ValueError("print master exceeds page")
        image_path = output / f"{fixture_id}.png"
        image.save(image_path)
        text = "\n\n".join([heading, *paragraphs])
        truth = canonical(
            {
                "version": "ocr-ground-truth-v1",
                "fixture_id": fixture_id,
                "page_number": 1,
                "transcription": {
                    "text": text,
                    "words": text.split(),
                    "lines": [line for block in blocks for line in block["lines"]],
                },
                "layout": {
                    "blocks": blocks,
                    "category": "phone_camera_photo",
                    "precedence": [[f"b{i}", f"b{i + 1}"] for i in range(len(blocks) - 1)],
                    "cells": [],
                },
                "legibility_notes": "Author-created print source; actual phone photograph pending.",
            }
        )
        truth_path = output / f"{fixture_id}.truth.json"
        truth_path.write_bytes(truth)
        records.append(
            {
                "fixture_id": fixture_id,
                "source_family_id": fixture_id,
                "split": "heldout",
                "status": "print_master_authored_photo_pending",
                "provenance": (
                    "Original project-authored educational text created for this "
                    "research fixture; Bitstream Vera; no external document or photograph"
                ),
                "source_digest": digest(image_path.read_bytes()),
                "ground_truth_digest": digest(truth),
                "word_count": len(text.split()),
                "image": image_path.name,
                "truth": truth_path.name,
            }
        )
    result = {"version": VERSION, "records": records}
    (output / "index.json").write_bytes(canonical(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(generate(args.output))
