"""Original development print sheets; these are never phone photographs."""

import argparse
from pathlib import Path

import reportlab
from PIL import Image, ImageDraw, ImageFont

from integrity import canonical, digest

VERSION = "ocr-phone-print-masters-development-v2"
PAGES = {
    "phone_camera_photo-development-01": (
        "How seeds travel",
        [
            (
                "A seed can begin a new plant when it reaches a place with water, air, and "
                "enough warmth. Plants have several ways to move their seeds away from the "
                "parent plant. A dandelion seed has a light, feathery top that can float on "
                "the wind."
            ),
            (
                "Other seeds travel with animals. Tiny hooks on a burdock seed can catch "
                "on fur, then fall off farther along the path. Some birds eat fruit and later "
                "leave the seeds in another place. The new location may give a young plant "
                "more room to grow."
            ),
            (
                "Look for different seed shapes on a walk. Which ones might fly, float, "
                "or cling to an animal?"
            ),
        ],
    ),
    "phone_camera_photo-development-02": (
        "Measuring rainfall",
        [
            (
                "Rainfall tells us how much water has fallen in a place. A simple rain "
                "gauge is a straight-sided container marked with a scale. Set it outdoors "
                "where a roof or tree will not block the rain. Check that it stands upright "
                "before a storm begins."
            ),
            (
                "Read the water level at the same time each day. Suppose the gauge shows "
                "12 mm on Monday and 8 mm on Tuesday. Together, those days brought 20 mm "
                "of rain. Write each reading in a notebook before emptying the container."
            ),
            (
                "Compare several days rather than one reading alone. Did a cloudy day "
                "always bring rain? What might happen to the garden after a dry week?"
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
                "split": "development",
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
