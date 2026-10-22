"""Development-only hash, geometry and font coverage audit."""

import argparse
import json
from pathlib import Path

import reportlab
from PIL import Image, ImageDraw, ImageFont

from development import prepare_cases
from integrity import canonical
from preprocessing.recipes import pixel_digest


def validate(index, manifest, output):
    prepared = prepare_cases(index, manifest)
    problems = []
    sheet = Image.new("RGB", (1600, 2400), "white")
    for i, (record, truth, path) in enumerate(prepared):
        with Image.open(path) as im:
            rgb = im.convert("RGB")
            width, height = rgb.size
            if pixel_digest(rgb) != record["input_pixel_digest"]:
                problems.append([record["fixture_id"], "pixel digest mismatch"])
            tile = rgb.copy()
            tile.thumbnail((310, 370))
            sheet.paste(tile, ((i % 5) * 320, (i // 5) * 400))
            ImageDraw.Draw(sheet).text(
                ((i % 5) * 320, (i // 5) * 400 + 375), record["fixture_id"][:40], fill="black"
            )
        for block in truth["layout"]["blocks"]:
            if any(not (0 <= x <= width and 0 <= y <= height) for x, y in block["polygon"]):
                problems.append([record["fixture_id"], "reference geometry outside page"])
            size = block.get("size", 26)
            font = (
                ImageFont.truetype(str(Path(reportlab.__file__).parent / "fonts/Vera.ttf"), size)
                if block.get("font") == "Bitstream Vera"
                else ImageFont.load_default_imagefont()
                if "bitmap" in block.get("font", "")
                else ImageFont.load_default(size=size)
            )
            try:
                missing = bytes(font.getmask("\uffff"))
            except UnicodeEncodeError:
                missing = None  # Bundled bitmap face is Latin-1 only.
            for char in set(block["text"]):
                if not char.isspace() and bytes(font.getmask(char)) == missing:
                    problems.append([record["fixture_id"], "unsupported glyph", char])
    report = dict(
        cases=len(prepared),
        distinct_sources=len({r["source_digest"] for r, _, _ in prepared}),
        category_p_cases=0,
        problems=problems,
        status="pass" if not problems else "fail",
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "validation.json").write_bytes(canonical(report))
    sheet.save(output / "contact-sheet.png")
    if problems:
        raise ValueError("corpus validation failed; see validation.json")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/benchmark.v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.index, args.manifest, args.output)))
