from pathlib import Path

from publication.score_profiles import REVIEW_QA_PROFILE

SEVERITY_LABELS = ("blocking", "major", "minor")

REVIEW_READONLY_SURFACES = [
    "inputs/**",
    "oracle/**",
    "verifiers/**",
    "candidate/review-target/**",
]

PROTECTED_SURFACES = [
    "inputs/**",
    "oracle/**",
    "verifiers/**",
    "candidate/review-target/**",
]


def build_review_bundle(bundle_root: Path) -> dict:
    metadata = {
        "role_class": "review",
        "artifact_type": "findings-only review report",
        "score_profile": REVIEW_QA_PROFILE.label,
        "allowed_change_surface": [
            "candidate/review-report.md",
            "candidate/repair-plan.md",
        ],
        "must_not_touch": PROTECTED_SURFACES,
    }
    write_bundle_readme(bundle_root)
    write_candidate_readme(bundle_root)
    (bundle_root / "candidate" / "repair-plan.md").write_text(
        "# Repair Plan\n\n- Convert each accepted finding into a direct patch step.\n",
        encoding="utf-8",
    )
    return metadata


def write_candidate_readme(bundle_root: Path) -> None:
    lines = ["Editable files:"]
    lines.extend(f"- {path}" for path in REVIEW_READONLY_SURFACES)
    lines.append("- review-report.md")
    lines.append("- repair-plan.md")
    (bundle_root / "candidate" / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
