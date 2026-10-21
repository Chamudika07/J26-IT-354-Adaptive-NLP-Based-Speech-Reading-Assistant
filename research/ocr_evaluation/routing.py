"""Research-only routing from actual Phase 2A outcomes."""


def eligibility(status: str, code: str | None, warnings: list[str]) -> str:
    if status == "failed":
        return "ineligible_failure"
    if "inspection_uncertain" in warnings or "replacement_character" in warnings:
        return "manual_review_only"
    if status == "ocr_required" and code == "image_without_text":
        return "eligible"
    if status == "needs_review" and "painted_image" in warnings:
        return "comparison_review_only"
    return "not_automatically_eligible"
