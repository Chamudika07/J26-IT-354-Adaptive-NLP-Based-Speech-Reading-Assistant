"""Draft synthetic pages, never silently promoted to verified benchmark cases."""

import argparse
from pathlib import Path

import reportlab
from PIL import Image, ImageDraw, ImageFont, __version__

from generators.degradations import points, transform
from integrity import canonical, digest, read_manifest
from preprocessing.recipes import pixel_digest

TOPICS = [
    ("Garden inventory", "Seven blue pots stand beside a wooden gate."),
    ("Coastal notebook", "A small boat crossed the quiet bay at dawn."),
    ("Library register", "The first shelf holds stories about mountains."),
    ("Weather station", "Clouds gathered above the eastern ridge."),
    ("Trail directions", "Follow the narrow path towards the stone bridge."),
    ("Workshop notice", "Place the clean tools on the lower bench."),
    ("Market list", "Buy four pears and a basket of fresh beans."),
    ("Orchard visit", "The oldest apple tree grows near the fence."),
    ("Museum guide", "The model ship has three white sails."),
    ("Railway notes", "The morning train stops beside platform six."),
    ("Window study", "Sunlight reaches the western desk after lunch."),
    ("Evening lamp", "A brass lamp illuminates the woven mat."),
    ("Map exercise", "Draw a square around the central fountain."),
    ("Parcel label", "Deliver the sealed parcel to the corner shop."),
    ("Stone collection", "Smooth pebbles fill a shallow silver dish."),
    ("Foggy morning", "A distant tower rises above the mist."),
    ("Radio bulletin", "A short message announces the weekly fair."),
    ("Archive folder", "An old folder contains twelve typed pages."),
    ("Plant journal", "Basil grows quickly beside the sunny window."),
    ("Concert card", "The flute recital begins after sunset."),
    ("Numerical checklist", "Batch #27: 12.5% + 8 = 20.5; cost $3.40."),
    ("Symbol exercise", "Order 18: 4/5, 6.25%, $9.80; yes/no?"),
    ("Cafe menu", "The café serves crème brûlée and warm tea."),
    ("Travel accents", "Zoë placed the résumé beside a blue beret."),
    ("Seed stock", "Bean 14 A2"),
    ("Supply table", "Brush 06 C3"),
    ("River and hill", "A willow marks the lower crossing."),
    ("Morning and night", "Sparrows gather around the empty feeder."),
    ("Triangle diagram", "The blue triangle points towards the label."),
    ("Circle diagram", "A green circle sits below the heading."),
]


def generate(output: Path, manifest_path: Path) -> dict:
    cases = [
        c
        for c in read_manifest(manifest_path).cases
        if c.split == "development" and c.category != "phone_camera_photo"
    ]
    output.mkdir(parents=True, exist_ok=False)
    records = []
    recipes = {
        "low_resolution": ("resolution", 100),
        "mild_blur": ("blur", 1.2),
        "skew_rotation": ("skew", 5),
        "uneven_lighting": ("illumination", "left_shadow"),
        "perspective_distortion": ("perspective", "mild"),
        "low_contrast": ("contrast", 0.4),
        "noise_compression": ("jpeg", 40),
    }
    for case, topic in zip(cases, TOPICS, strict=True):
        image = Image.new("RGB", (1600, 2000), "white")
        draw = ImageDraw.Draw(image)
        blocks, cells = [], []

        def add(
            text,
            x,
            y,
            *,
            size=26,
            role="body",
            block_id=None,
            bitmap=False,
            draw=draw,
            image=image,
            blocks=blocks,
            category=case.category,
        ):
            if category == "accented_english_unicode":
                font = ImageFont.truetype(
                    str(Path(reportlab.__file__).parent / "fonts/Vera.ttf"), size
                )
            else:
                font = (
                    ImageFont.load_default_imagefont()
                    if bitmap
                    else ImageFont.load_default(size=size)
                )
            left, top, right, bottom = draw.textbbox((x, y), text, font=font)
            if bitmap:
                # A distinct bundled bitmap face, enlarged by an explicitly recorded factor.
                tile = Image.new("RGB", (right - left + 2, bottom - top + 2), "white")
                ImageDraw.Draw(tile).text(
                    (1 - left + x, 1 - top + y), text, font=font, fill="black"
                )
                tile = tile.resize((tile.width * 3, tile.height * 3), Image.Resampling.NEAREST)
                image.paste(tile, (x, y))
                left, top, right, bottom = x, y, x + tile.width, y + tile.height
            else:
                draw.text((x, y), text, font=font, fill="black")
            if left < 0 or top < 0 or right > image.width or bottom > image.height:
                raise ValueError("authored text exceeds page")
            block = dict(
                id=block_id or f"b{len(blocks)}",
                text=text,
                lines=[text],
                role=role,
                font=(
                    "Bitstream Vera"
                    if category == "accented_english_unicode"
                    else "PIL bitmap x3 nearest"
                    if bitmap
                    else "Aileron"
                ),
                size=size,
                polygon=[[left, top], [right, top], [right, bottom], [left, bottom]],
            )
            blocks.append(block)
            return block

        add(topic[0], 90, 100, size=36, role="spanning_heading", block_id="heading")
        if case.category == "tables":
            values = [
                ["Item", "Count", "Tray"],
                topic[1].split(),
                ["Pea", "09", "B4"] if case.fixture_id.endswith("01") else ["Cloth", "11", "D7"],
            ]
            for row, values_row in enumerate(values):
                for column, text in enumerate(values_row):
                    x, y = 90 + column * 280, 240 + row * 100
                    draw.rectangle((x - 10, y - 10, x + 270, y + 90), outline="gray", width=2)
                    block = add(text, x, y, block_id=f"r{row}c{column}", role="table_cell")
                    cells.append(
                        dict(
                            id=block["id"],
                            row=row,
                            column=column,
                            text=text,
                            polygon=block["polygon"],
                        )
                    )
        elif case.category == "two_column":
            add(
                "Lower route" if case.fixture_id.endswith("01") else "Morning watch",
                90,
                220,
                size=30,
                role="left_column",
                block_id="left-heading",
            )
            add(topic[1], 90, 300, role="left_column", block_id="left-body")
            add("Follow the marked path beside the water.", 90, 370, role="left_column")
            add(
                "Upper route" if case.fixture_id.endswith("01") else "Night watch",
                830,
                220,
                size=30,
                role="right_column",
                block_id="right-heading",
            )
            add(
                "A stone seat stands beside the hill."
                if case.fixture_id.endswith("01")
                else "An owl waits above the silent field.",
                830,
                300,
                role="right_column",
            )
            add("Keep a separate note for this route.", 830, 370, role="right_column")
            add("Figure 1: Two observation areas.", 90, 600, size=22, role="caption")
            add("Note: These are fictional field observations.", 90, 1800, size=20, role="footnote")
        else:
            add(topic[1], 90, 240)
            if case.category == "mixed_fonts_sizes":
                add("READ THE SMALL LABEL", 90, 360, bitmap=True)
                add("The final line uses a larger size.", 90, 460, size=40)
            if case.category == "illustration_text":
                if case.fixture_id.endswith("01"):
                    draw.polygon([(200, 700), (400, 700), (300, 500)], fill="blue")
                    caption = "Figure 1: A triangle with three sides."
                else:
                    draw.ellipse((200, 500, 400, 700), fill="green")
                    caption = "Figure 1: A circle with a curved boundary."
                add(caption, 90, 760, size=22, role="caption")
        lines = [block["text"] for block in blocks]
        parent = pixel_digest(image)
        degradation = None
        if case.category == "grayscale_scan":
            image = image.convert("L").point(lambda v: 35 + round(v * 0.8)).convert("RGB")
        if case.category in recipes:
            image, degradation = transform(image, *recipes[case.category])
            for block in blocks + cells:
                block["polygon"] = points(block["polygon"], degradation["forward_matrix"])
        path = output / (case.fixture_id + ".png")
        image.save(path)
        truth = canonical(
            dict(
                version="ocr-ground-truth-v1",
                fixture_id=case.fixture_id,
                page_number=1,
                transcription=dict(
                    text="\n\n".join(lines), words=" ".join(lines).split(), lines=lines
                ),
                layout=dict(
                    blocks=blocks,
                    category=case.category,
                    precedence=[
                        [a["id"], b["id"]] for a, b in zip(blocks, blocks[1:], strict=False)
                    ],
                    cells=cells,
                ),
                legibility_notes="Unreviewed draft; not eligible for benchmark freeze.",
            )
        )
        (output / (case.fixture_id + ".truth.json")).write_bytes(truth)
        records.append(
            dict(
                fixture_id=case.fixture_id,
                source_family_id=case.source_family_id,
                split=case.split,
                category=case.category,
                source_digest=digest(path.read_bytes()),
                ground_truth_digest=digest(truth),
                input_pixel_digest=pixel_digest(image),
                parent_pixel_digest=parent,
                transformation=degradation,
                status="draft",
                provenance="Original synthetic authoring; CC0-1.0",
                font=(
                    "ReportLab bundled Bitstream Vera; Bitstream Vera license"
                    if case.category == "accented_english_unicode"
                    else "Pillow Aileron / PIL bitmap; see fonts.v1.json"
                ),
                pillow_version=__version__,
            )
        )
    result = dict(
        version="ocr-development-drafts-v3",
        synthetic_drafts=30,
        phone_print_masters=0,
        deferred_phone_cases=2,
        verified_cases=0,
        records=records,
    )
    (output / "index.json").write_bytes(canonical(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/benchmark.v1.json"))
    args = parser.parse_args()
    result = generate(args.output, args.manifest)
    print({k: v for k, v in result.items() if k != "records"})
