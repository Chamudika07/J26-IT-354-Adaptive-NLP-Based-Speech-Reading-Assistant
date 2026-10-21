"""Fresh-process CPU worker. No model-source resolution; all directories are explicit.

Python socket audit is defense in depth, not an OS-level network isolation guarantee.
Final Linux evaluation must additionally disable network at the container boundary.
"""

import contextlib
import json
import resource
import sys
import time
from importlib.metadata import version
from pathlib import Path


def deny_network(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise RuntimeError("frozen_evaluation_network_forbidden")


def main():
    # This directory contains paddle.py, which must not shadow the installed runtime.
    sys.path = [p for p in sys.path if Path(p).resolve() != Path(__file__).resolve().parent]
    sys.addaudithook(deny_network)
    config = json.loads(Path(sys.argv[1]).read_bytes())
    recognition_model_name = config["recognition_model_name"]
    if recognition_model_name not in {
        "en_PP-OCRv4_mobile_rec",
        "en_PP-OCRv5_mobile_rec",
    }:
        raise ValueError("unsupported_recognizer")
    if version("paddleocr") != "3.2.0" or version("paddlepaddle") != "3.2.0":
        raise ValueError("engine_version_mismatch")
    with contextlib.redirect_stdout(sys.stderr):
        from paddleocr import PaddleOCR

        load_start = time.perf_counter()
        engine = PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_detection_model_dir=config["detection_dir"],
            text_recognition_model_name=recognition_model_name,
            text_recognition_model_dir=config["recognition_dir"],
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_rec_score_thresh=0.0,
            text_det_limit_side_len=960,
            text_det_limit_type="max",
            text_det_thresh=0.3,
            text_det_box_thresh=0.6,
            text_det_unclip_ratio=1.5,
            device="cpu",
            cpu_threads=1,
            enable_mkldnn=False,
        )
        load_ms = (time.perf_counter() - load_start) * 1000
        ocr_start = time.perf_counter()
        results = list(engine.predict(config["image"]))
        ocr_ms = (time.perf_counter() - ocr_start) * 1000
        if len(results) != 1:
            raise ValueError("unexpected page count")
        native = results[0].json
        if isinstance(native, str):
            native = json.loads(native)
        payload = native.get("res", native)
    payload["research_measurements"] = {
        "load_ms": load_ms,
        "ocr_ms": ocr_ms,
        "worker_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        * (1 if sys.platform == "darwin" else 1024),
        "memory_method": "worker-only getrusage peak RSS; excludes process tree",
    }
    print(json.dumps(payload, allow_nan=False))


if __name__ == "__main__":
    main()
