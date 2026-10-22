"""Researcher-supplied photographs only. Never manufactures or fetches photo inputs."""

from pathlib import Path

from preprocessing.recipes import decode

PHOTO_SPLITS = {"development": 2, "heldout": 3}


def expected_photos(root: Path) -> list[Path]:
    return [
        root / "artifacts" / "phone_photos" / split / f"phone_camera_photo-{split}-{i:02}.jpg"
        for split, count in PHOTO_SPLITS.items()
        for i in range(1, count + 1)
    ]


def require_phone_photos(root: Path) -> None:
    missing = [path.name for path in expected_photos(root) if not path.is_file()]
    if missing:
        raise ValueError("required researcher phone photographs missing: " + ", ".join(missing))
    for path in expected_photos(root):
        # Valid pixels alone do not establish researcher provenance: separate review required.
        image = decode(path, "image/jpeg")
        image.close()
