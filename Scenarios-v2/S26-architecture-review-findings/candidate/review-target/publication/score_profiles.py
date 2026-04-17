from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreProfile:
    label: str
    correctness: int
    role_fidelity: int
    scope_discipline: int
    synthesis_quality: int
    verification_cleanliness: int
    runtime_cleanliness: int


REVIEW_QA_PROFILE = ScoreProfile(
    label="review, QA",
    correctness=30,
    role_fidelity=20,
    scope_discipline=20,
    synthesis_quality=20,
    verification_cleanliness=5,
    runtime_cleanliness=5,
)
