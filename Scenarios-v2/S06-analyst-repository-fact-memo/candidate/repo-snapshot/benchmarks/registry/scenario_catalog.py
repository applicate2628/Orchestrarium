from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScenarioRecord:
    id: str
    surface_id: str
    score_profile: str
    artifact_type: str
    modality_family: str
    bundle_root: Path

    @classmethod
    def from_metadata(cls, raw: dict, bundle_root: Path) -> "ScenarioRecord":
        return cls(
            id=raw["id"],
            surface_id=raw["surface_id"],
            score_profile=raw["score_profile"],
            artifact_type=raw["artifact_type"],
            modality_family=raw["modality_family"],
            bundle_root=bundle_root,
        )
