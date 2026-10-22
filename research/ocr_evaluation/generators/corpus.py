"""Author source packets only; category-realistic rendering requires reviewed source designs.
No held-out packet is emitted by this development command. Phone slots require real photos.
"""

import argparse
import json
from pathlib import Path

from integrity import canonical, digest, read_manifest

VERSION = "ocr-authoring-v1"


def author_development(manifest: Path, output: Path) -> list[dict]:
    corpus = read_manifest(manifest)
    output.mkdir(parents=True, exist_ok=False)
    records = []
    # Source packets are NOT validated benchmark images and are never counted as cases.
    for number, c in enumerate(sorted(corpus.cases, key=lambda x: x.fixture_id), 1):
        if c.split != "development" or c.category == "phone_camera_photo":
            continue
        text = (
            f"Field note {number}: The quiet garden.\n"
            f"A gardener counted {number + 7} seeds beside the blue gate.\n"
            "At 9:30, the team wrote: “Keep 12.5% for café plants!”"
        )
        packet = {
            "fixture_id": c.fixture_id,
            "version": VERSION,
            "provenance": "Original synthetic authoring source; CC0-1.0",
            "transcription": {"text": text, "words": text.split(), "lines": text.split("\n")},
            "layout": {
                "status": "requires_category_specific_authoring",
                "blocks": [],
                "precedence": [],
                "cells": [],
                "polygons": [],
            },
            "page_number": 1,
            "legibility_notes": "Not rendered or reviewed",
        }
        data = canonical(packet)
        (output / (c.fixture_id + ".json")).write_bytes(data)
        records.append({"fixture_id": c.fixture_id, "authoring_digest": digest(data)})
    (output / "index.json").write_text(json.dumps(records, indent=2) + "\n")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("manifests/benchmark.v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    author_development(args.manifest, args.output)
