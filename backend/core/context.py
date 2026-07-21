"""``ReviewContext`` — shared state flowing through every pipeline step."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.schemas import Finding


class ReviewContext(BaseModel):
    """Mutable review run state. Pure data — no DB / HTTP."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    workdir: Path
    deck_path: Path | None = None
    audio_path: Path | None = None
    xlsx_path: Path | None = None
    review_id: UUID | None = None
    findings: list[Finding] = Field(default_factory=list)
    step_results: dict[str, Any] = Field(default_factory=dict)
    slide_pngs: dict[int, Path] = Field(default_factory=dict)
    cost_rub: float = 0.0
    meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_cost_rub(self) -> float:
        return self.cost_rub

    def add_cost(self, amount_rub: float) -> None:
        self.cost_rub += max(0.0, amount_rub)

    def add_findings(self, items: list[Finding], source: str) -> None:
        for item in items:
            data = item.model_dump()
            if not data.get("source"):
                data["source"] = source
            self.findings.append(Finding.model_validate(data))

    def slide_png(self, n: int) -> Path:
        try:
            return self.slide_pngs[n]
        except KeyError as exc:
            raise FileNotFoundError(f"No PNG registered for slide {n}") from exc

    def dump(self, path: Path | None = None) -> Path:
        """Serialize context JSON into workdir (or ``path``)."""
        target = path or (self.workdir / "review_context.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "workdir": str(self.workdir),
            "deck_path": str(self.deck_path) if self.deck_path else None,
            "audio_path": str(self.audio_path) if self.audio_path else None,
            "xlsx_path": str(self.xlsx_path) if self.xlsx_path else None,
            "review_id": str(self.review_id) if self.review_id else None,
            "findings": [f.model_dump(mode="json") for f in self.findings],
            "step_results": self.step_results,
            "slide_pngs": {str(k): str(v) for k, v in self.slide_pngs.items()},
            "cost_rub": self.cost_rub,
            "meta": self.meta,
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: Path) -> ReviewContext:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            workdir=Path(data["workdir"]),
            deck_path=Path(data["deck_path"]) if data.get("deck_path") else None,
            audio_path=Path(data["audio_path"]) if data.get("audio_path") else None,
            xlsx_path=Path(data["xlsx_path"]) if data.get("xlsx_path") else None,
            review_id=UUID(data["review_id"]) if data.get("review_id") else None,
            findings=[Finding.model_validate(f) for f in data.get("findings", [])],
            step_results=data.get("step_results", {}),
            slide_pngs={int(k): Path(v) for k, v in data.get("slide_pngs", {}).items()},
            cost_rub=float(data.get("cost_rub", 0.0)),
            meta=data.get("meta", {}),
        )
