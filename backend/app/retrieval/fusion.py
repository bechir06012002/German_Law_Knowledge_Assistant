"""Reciprocal Rank Fusion.

The two retrieval legs produce incomparable numbers — cosine similarity is bounded,
`ts_rank_cd` is not — so their scores cannot be added or averaged. RRF ignores the scores and
uses only the ranks, which is exactly what makes it work across legs of different kinds.

    score(d) = Σ  1 / (k + rank_leg(d))

`k = 60` is the value from the original paper and the one the previous project used; it damps
the influence of a single leg's top result enough that a document has to do well in both legs
to reach the top of the fused list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

RRF_K = 60

T = TypeVar("T")


@dataclass
class Fused:
    key: str
    score: float
    """Rank this item achieved in each leg, 1-based. Kept for debugging a bad result set —
    without it there is no way to tell "both legs agreed" from "one leg was very confident"."""
    ranks: dict[str, int] = field(default_factory=dict)


def reciprocal_rank_fusion(
    leg_results: dict[str, list[str]], *, k: int = RRF_K
) -> list[Fused]:
    """Fuse ranked lists of keys into one ranked list.

    `leg_results` maps a leg name to its ranked keys, best first. A key missing from a leg
    simply contributes nothing for that leg — it is not penalised beyond that.
    """
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}

    for leg, keys in leg_results.items():
        for position, key in enumerate(keys, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + position)
            ranks.setdefault(key, {})[leg] = position

    fused = [Fused(key=key, score=score, ranks=ranks[key]) for key, score in scores.items()]
    # Ties broken by best single rank, then by key, so the order is deterministic across runs.
    fused.sort(key=lambda f: (-f.score, min(f.ranks.values()), f.key))
    return fused
