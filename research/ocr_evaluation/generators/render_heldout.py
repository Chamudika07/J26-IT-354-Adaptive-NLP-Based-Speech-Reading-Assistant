"""Held-out source renderer; preserves development-v3 geometry and degradation semantics."""

import argparse
from pathlib import Path

import reportlab
from PIL import Image, ImageDraw, ImageFont, __version__

from generators.degradations import points, transform
from integrity import canonical, digest, read_manifest
from preprocessing.recipes import pixel_digest

TOPICS = [
    ("Sound vibrations", "A plucked string moves back and forth to make sound."),
    ("Magnetic forces", "A magnet can attract an iron nail across a small gap."),
    ("Earth layers", "Solid rock forms the outer crust of our planet."),
    ("Moon phases", "We see different amounts of the lit half of the Moon."),
    ("Fossil clues", "A footprint in ancient mud can become a fossil."),
    ("Ocean depths", "Less sunlight reaches water far below the surface."),
    ("Lever experiment", "A longer handle can make a heavy load easier to lift."),
    ("Water cycle", "Water vapour cools and forms tiny liquid drops."),
    ("Animal shelters", "A hollow log provides shelter for many small animals."),
    ("Roots underground", "Roots take in water and help anchor a plant in soil."),
    ("Bee signals", "A honeybee can share information by moving its body."),
    ("Rock changes", "Flowing water slowly wears away exposed rock."),
    ("Star patterns", "People group bright stars into named patterns."),
    ("Shadows move", "A shadow changes direction as the Sun crosses the sky."),
    ("Soil layers", "Decaying leaves enrich the upper layer of woodland soil."),
    ("Feather shapes", "Broad wing feathers help many birds stay in the air."),
    ("Heat transfer", "A metal spoon carries heat from warm soup to its handle."),
    ("Earthworm tunnels", "Earthworms mix soil as they dig winding tunnels."),
    ("Air pressure", "Moving air pushes against the surface of a paper sail."),
    ("River bends", "A river can carry sand around a wide bend."),
    ("Skeleton support", "Bones support the body and protect delicate organs."),
    ("Balanced forces", "Equal pushes in opposite directions can balance."),
    ("Leaf surfaces", "A waxy surface helps some leaves retain water."),
    ("Tide pools", "Small creatures shelter in pools left by the falling tide."),
    ("Echo timing", "Sound reflects from a hard wall and returns as an echo."),
    ("Shell spirals", "A growing snail adds new material to its shell."),
    ("Compost changes", "Fungi help break dead plant material into smaller pieces."),
    ("Simple circuits", "A closed path allows current to flow through a bulb."),
    ("Ice expansion", "Water takes up more space when it freezes into ice."),
    ("Camouflage colours", "A moth can blend with bark while resting on a trunk."),
    ("Fraction puzzle", "Trial #31: 3/4 + 0.25 = 1; score 75%; cost $2.60."),
    ("Measuring length", "Mark #42: 2.5 cm + 7.5 cm = 10 cm; ratio 1:3."),
    ("Temperature record", "Readings: 18.5, 21.0, 19.5; mean = 19.67; change +2.5!"),
    ("Borrowed words", "The word façade describes the front of a building."),
    ("Language notebook", "Renée wrote naïve and cliché with their accents."),
    ("Music vocabulary", "An étude is a musical exercise for a performer."),
    ("Mineral samples", "Quartz 17 E5"),
    ("Habitat samples", "Moss 23 F8"),
    ("Recycling samples", "Paper 32 G6"),
    ("Pond zones", "Reeds grow near the bank."),
    ("Desert zones", "Dunes shift with the wind."),
    ("Forest zones", "Ferns grow in damp shade."),
    ("Shape investigation", "Count the corners of the coloured shape below."),
    ("Round objects", "Trace the curved edge of the shape with a finger."),
    ("Geometry practice", "Describe the boundary of the shape in one sentence."),
]


def generate(output: Path, manifest_path: Path) -> dict:
    cases = [
        c
        for c in read_manifest(manifest_path).cases
        if c.split == "heldout" and c.category != "phone_camera_photo"
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
                ["Sample", "Number", "Box"],
                topic[1].split(),
                ["Feldspar", "28", "H9"]
                if case.fixture_id.endswith("01")
                else ["Bark", "35", "J2"],
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
                "Near zone" if case.fixture_id.endswith("01") else "Ground level",
                90,
                220,
                size=30,
                role="left_column",
                block_id="left-heading",
            )
            add(topic[1], 90, 300, role="left_column", block_id="left-body")
            add("Sketch one feature of this habitat.", 90, 370, role="left_column")
            add(
                "Far zone" if case.fixture_id.endswith("01") else "High level",
                830,
                220,
                size=30,
                role="right_column",
                block_id="right-heading",
            )
            add(
                "Water lilies float farther out."
                if case.fixture_id.endswith("01")
                else "Conditions differ above the ground.",
                830,
                300,
                role="right_column",
            )
            add("Compare the two areas carefully.", 830, 370, role="right_column")
            add("Figure 2: Comparing habitat zones.", 90, 600, size=22, role="caption")
            add(
                "Activity: Describe one difference between these zones.",
                90,
                1800,
                size=20,
                role="footnote",
            )
        else:
            add(topic[1], 90, 240)
            if case.category == "mixed_fonts_sizes":
                add("CHECK EACH CONNECTION", 90, 360, bitmap=True)
                add("Explain the observation aloud.", 90, 460, size=40)
            if case.category == "illustration_text":
                if case.fixture_id.endswith("01"):
                    draw.polygon([(200, 700), (400, 700), (300, 500)], fill="blue")
                    caption = "Diagram: Three straight edges meet at corners."
                else:
                    draw.ellipse((200, 500, 400, 700), fill="green")
                    caption = "Diagram: A round edge has no corners."
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
                legibility_notes="Prepared held-out source; no OCR executed.",
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
                status="prepared",
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
        version="ocr-heldout-sources-v1",
        synthetic_cases=45,
        phone_print_masters=0,
        deferred_phone_cases=3,
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
