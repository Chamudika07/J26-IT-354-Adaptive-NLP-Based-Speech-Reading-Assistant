"""Deterministic single-factor transformations; geometry follows forward homography."""

import io

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from preprocessing.recipes import bounded, pixel_digest

VERSION = "ocr-degradation-v1"
LEVELS = {
    "resolution": [300, 200, 150, 100],
    "skew": [0, 2, -2, 5, -5],
    "orientation": [90, 180, 270],
    "blur": [0, 0.6, 1.2],
    "contrast": [1.0, 0.7, 0.4],
    "brightness": [0.8, 1.0, 1.2],
    "jpeg": [95, 70, 40],
    "noise": [0, 5, 10],
    "perspective": ["mild"],
    "illumination": ["left_shadow"],
}


def points(polygon: list, matrix: list) -> list:
    m = np.asarray(matrix, dtype=float)
    result = []
    for x, y in polygon:
        p = m @ [x, y, 1]
        if abs(p[2]) < 1e-12:
            raise ValueError("singular geometry")
        result.append([float(p[0] / p[2]), float(p[1] / p[2])])
    return result


def transform(image: Image.Image, kind: str, level: object, seed: int = 22081766) -> tuple:
    bounded(image)
    if kind not in LEVELS or level not in LEVELS[kind]:
        raise ValueError("undeclared degradation")
    matrix = np.eye(3)
    result = image.copy()
    interpolation = "none"
    if kind == "resolution":
        size = (round(image.width * level / 300), round(image.height * level / 300))
        if min(size) < 1:
            raise ValueError("zero-sized resolution")
        result = image.resize(size, Image.Resampling.LANCZOS)
        matrix = np.diag([size[0] / image.width, size[1] / image.height, 1])
        interpolation = "LANCZOS"
    elif kind in {"skew", "orientation"}:
        # Fixed canvas, matching PIL pixel-centre rotation around width/2,height/2.
        angle = np.deg2rad(float(level))
        c, s = np.cos(angle), np.sin(angle)
        cx, cy = image.width / 2, image.height / 2
        matrix = np.array([[c, s, cx - c * cx - s * cy], [-s, c, cy + s * cx - c * cy], [0, 0, 1]])
        inverse = np.linalg.inv(matrix)
        result = image.transform(
            image.size,
            Image.Transform.AFFINE,
            tuple(inverse[:2].ravel()),
            Image.Resampling.BICUBIC,
            fillcolor="white",
        )
        interpolation = "BICUBIC"
    elif kind == "perspective":
        # Forward, fixed fractional corner displacement; keep exact matrix in evidence.
        matrix = np.array(
            [
                [0.90, 0.04, 0.02 * image.width],
                [0.02, 0.92, 0.02 * image.height],
                [0.00002, 0.00001, 1.0],
            ]
        )
        inverse = np.linalg.inv(matrix)
        inverse /= inverse[2, 2]
        result = image.transform(
            image.size,
            Image.Transform.PERSPECTIVE,
            tuple(inverse.ravel()[:8]),
            Image.Resampling.BICUBIC,
            fillcolor="white",
        )
        interpolation = "BICUBIC"
    elif kind == "blur":
        result = image.filter(ImageFilter.GaussianBlur(float(level)))
    elif kind in {"contrast", "brightness"}:
        cls = ImageEnhance.Contrast if kind == "contrast" else ImageEnhance.Brightness
        result = cls(image).enhance(float(level))
    elif kind == "jpeg":
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=level, subsampling=0, optimize=False)
        with Image.open(io.BytesIO(out.getvalue())) as decoded:
            result = decoded.convert("RGB")
    elif kind == "noise":
        noise = np.random.default_rng(seed).normal(0, float(level), (image.height, image.width, 3))
        result = Image.fromarray(
            np.clip(np.asarray(image, dtype=float) + noise, 0, 255).astype("uint8")
        )
    elif kind == "illumination":
        mask = np.linspace(0.55, 1.0, image.width)[None, :, None]
        result = Image.fromarray((np.asarray(image, dtype=float) * mask).astype("uint8"))
    record = {
        "version": VERSION,
        "order": [kind],
        "parameters": {kind: level},
        "seed": seed,
        "interpolation": interpolation,
        "forward_matrix": matrix.tolist(),
        "parent_pixel_sha256": pixel_digest(image),
        "output_pixel_sha256": pixel_digest(result),
    }
    return result, record
