"""Opt-in offline file adapter over shared fictional-evidence calculations."""

import argparse
from datetime import timedelta
from pathlib import Path

from app.modules.learner_modelling.demo_calculation import (
    ConnectedPreview as ConnectedPreview,
)
from app.modules.learner_modelling.demo_calculation import (
    DemoContext as DemoContext,
)
from app.modules.learner_modelling.demo_calculation import (
    SampleFile as SampleFile,
)
from app.modules.learner_modelling.demo_calculation import (
    build_connected_preview as build_connected_preview,
)
from app.modules.learner_modelling.demo_calculation import (
    build_connected_replay as build_connected_replay,
)
from app.modules.learner_modelling.longitudinal import LongitudinalWindow


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Development synthetic files only; no network/database"
    )
    parser.add_argument("--development-synthetic-only", action="store_true", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument(
        "--task",
        choices=["independent_reading", "assisted_read_aloud", "guided_echo_reading"],
        required=False,
    )
    parser.add_argument("--tier", choices=["early", "intermediate", "advanced"])
    parser.add_argument("--mode", choices=["baseline_fixed", "adaptive", "manual_override"])
    parser.add_argument(
        "--derive-window-context",
        action="store_true",
        help="Use exact validated sample dates and one shared input context",
    )
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > 100_000:
            raise ValueError()
        raw = args.input.read_text(encoding="utf-8")
        if args.derive_window_context:
            if any(
                value is not None
                for value in (args.start, args.end, args.task, args.tier, args.mode)
            ):
                raise ValueError("Conflicting window/context selection")
            sample = SampleFile.model_validate_json(raw)
            contexts = {(r.task, r.tier, r.mode) for r in sample.records}
            if not sample.records or len(contexts) != 1:
                raise ValueError("Explicit window/context required for empty or mixed input")
            task, tier, mode = next(iter(contexts))
            context = DemoContext(task=task, tier=tier, mode=mode)
            window = LongitudinalWindow(
                start_at_utc=min(r.start for r in sample.records),
                end_at_utc=max(r.end for r in sample.records) + timedelta(milliseconds=1),
            )
        else:
            if any(
                value is None for value in (args.start, args.end, args.task, args.tier, args.mode)
            ):
                raise ValueError("Explicit window and context required")
            window = LongitudinalWindow.model_validate(
                {"start_at_utc": args.start, "end_at_utc": args.end}
            )
            context = DemoContext(task=args.task, tier=args.tier, mode=args.mode)
        artifact = build_connected_preview(raw, window, context)
        base = Path(__file__).resolve().parents[4] / "mobile/src/features/learnerModelling/preview"
        # Source sidecar is for offline reproducibility tests only; never imported by mobile UI.
        (base / "connectedSessionInput.json").write_text(raw, encoding="utf-8")
        replay = build_connected_replay(
            raw,
            LongitudinalWindow(
                start_at_utc=artifact.reportingStartUtc, end_at_utc=artifact.reportingEndUtc
            ),
            artifact.context,
            generated_at=artifact.generatedAt,
        )
        replay_json = "[" + ",".join(step.model_dump_json(indent=2) for step in replay) + "]\n"
        for name in ("connectedSessionReplay.json", "connectedSessionReplayContract.json"):
            (base / name).write_text(replay_json, encoding="utf-8")
        payload = artifact.model_dump_json(indent=2) + "\n"
        # Explicit opt-in replaces only this separate connected-demo artifact and pin.
        for name in ("connectedSessionPreview.json", "connectedSessionContract.json"):
            (base / name).write_text(payload, encoding="utf-8")
    except Exception:
        parser.exit(
            2,
            "Synthetic import rejected or artifact could not be written. "
            "Check file, schema, window and context.\n",
        )


if __name__ == "__main__":
    main()
