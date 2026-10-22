"""Versioned single-factor preprocessing and direct-image policy."""

import io
import warnings
from pathlib import Path

from PIL import Image, ImageCms, ImageEnhance, ImageOps, UnidentifiedImageError

from integrity import canonical, digest

VERSION = "ocr-preprocessing-v1"
MAX_BYTES = 10 * 1024 * 1024


def bounded(image: Image.Image) -> None:
    w, h = image.size
    if min(w, h) < 1 or max(w, h) > 6000 or w * h > 12_000_000:
        raise ValueError("image_resource_limit")


def decode(path: Path, mime: str) -> Image.Image:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("compressed_size_limit")
    data = path.read_bytes()
    png = data.startswith(b"\x89PNG\r\n\x1a\n")
    jpeg = data.startswith(b"\xff\xd8\xff")
    if not ((mime == "image/png" and png) or (mime == "image/jpeg" and jpeg)):
        raise ValueError("mime_magic_mismatch")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                bounded(source)
                if source.format not in {"PNG", "JPEG"} or getattr(source, "n_frames", 1) != 1:
                    raise ValueError("unsupported_image")
                image = ImageOps.exif_transpose(source)
                image.load()
                if image.info.get("icc_profile"):
                    profile = ImageCms.ImageCmsProfile(io.BytesIO(image.info["icc_profile"]))
                    image = ImageCms.profileToProfile(
                        image, profile, ImageCms.createProfile("sRGB"), outputMode="RGBA"
                    )
                rgba = image.convert("RGBA")
                white = Image.new("RGBA", rgba.size, "white")
                white.alpha_composite(rgba)
                rgb = white.convert("RGB")
                rgb.info.clear()
                return rgb
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise ValueError("malformed_image") from exc


def pixel_digest(image: Image.Image) -> str:
    return digest(canonical({"size": image.size, "mode": image.mode}) + image.tobytes())


def apply(image: Image.Image, recipe: str = "baseline", **parameters: float) -> tuple:
    bounded(image)
    allowed = {
        "baseline": set(),
        "grayscale": set(),
        "contrast": {"factor"},
        "resize": {"scale"},
        "deskew": {"angle"},
        "adaptive_threshold": {"window", "offset"},
    }
    if recipe not in allowed or set(parameters) != allowed[recipe]:
        raise ValueError("unknown recipe or incomplete parameters")
    result = image.copy()
    if recipe == "grayscale":
        result = ImageOps.grayscale(image).convert("RGB")
    elif recipe == "contrast":
        if not 0 < parameters["factor"] <= 3:
            raise ValueError("invalid contrast")
        result = ImageEnhance.Contrast(image).enhance(parameters["factor"])
    elif recipe == "deskew":
        if abs(parameters["angle"]) > 5:
            raise ValueError("deskew angle outside development range")
        result = image.rotate(
            parameters["angle"], Image.Resampling.BICUBIC, expand=False, fillcolor="white"
        )
    elif recipe == "resize":
        scale = parameters["scale"]
        size = (round(image.width * scale), round(image.height * scale))
        if min(size) < 1 or max(size) > 6000 or size[0] * size[1] > 12_000_000:
            raise ValueError("image_resource_limit")
        result = image.resize(size, Image.Resampling.LANCZOS)
    elif recipe == "adaptive_threshold":
        import numpy as np
        from PIL import ImageFilter

        window = parameters["window"]
        if window not in (3, 5, 7, 9, 11):
            raise ValueError("invalid window")
        gray = ImageOps.grayscale(image)
        local = gray.filter(ImageFilter.BoxBlur(int(window) // 2))
        mask = np.asarray(gray, dtype=float) > np.asarray(local, dtype=float) - parameters["offset"]
        result = Image.fromarray((mask * 255).astype("uint8")).convert("RGB")
    return result, {
        "recipe": recipe,
        "version": VERSION,
        "parameters": parameters,
        "input_pixel_digest": pixel_digest(image),
        "output_pixel_digest": pixel_digest(result),
    }
