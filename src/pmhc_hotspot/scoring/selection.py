"""Final RFdiffusion hotspot selection with biological constraints."""

from __future__ import annotations

import logging

from pmhc_hotspot.constants import (
    DEFAULT_HOTSPOT_CONFIG,
    HYDROPHOBIC_FOR_INTERFACE,
    RESIDUE_CHEMICAL_SCORE,
    SKIP_ALWAYS,
)
from pmhc_hotspot.features.allele_rules import AnchorFilter
from pmhc_hotspot.types import ResidueScore

logger = logging.getLogger(__name__)


def _count_hydrophobic(amino_acids: str) -> int:
    return sum(1 for aa in amino_acids if aa in HYDROPHOBIC_FOR_INTERFACE)


def _effective_hydrophobic_requirement(n_selected: int, min_hydrophobic: int) -> int:
    """Scale hydrophobic count down for smaller hotspot sets (3-4 residues)."""
    if n_selected <= 0:
        return 0
    if n_selected <= 3:
        return min(min_hydrophobic, 2, n_selected)
    if n_selected == 4:
        return min(min_hydrophobic, 2)
    return min(min_hydrophobic, n_selected)


def _position_eligible(
    position_1based: int,
    aa: str,
    peptide_length: int,
    allele: str | None,
    *,
    allow_n_terminal_small: bool = False,
) -> bool:
    if aa in SKIP_ALWAYS:
        return False
    if position_1based == 1 and aa in {"A", "G"} and not allow_n_terminal_small:
        return False
    return True


def _anchor_rank_multiplier(
    residue: ResidueScore,
    peptide_length: int,
    allele: str | None,
    anchor_filter: AnchorFilter,
) -> float:
    position_1based = residue.position_index + 1
    return anchor_filter.selection_multiplier(
        position_1based,
        peptide_length,
        buried=residue.is_buried,
        relative_sasa=residue.relative_sasa,
    )


def select_rfdiffusion_hotspots(
    residue_scores: list[ResidueScore],
    *,
    allele: str | None = None,
    min_hotspots: int | None = None,
    max_hotspots: int | None = None,
    min_hydrophobic: int | None = None,
) -> list[ResidueScore]:
    """
    Select 3-6 RFdiffusion hotspots with biological design constraints.

    Rules (from pMHC binder design literature and RFdiffusion PPI practice):
    - Softly down-weight MHC-I anchor positions (allele-aware; not hard-excluded)
    - Skip Pro/Gly; skip N-terminal Ala/Gly (flexible, low contact area)
    - Prefer high-scoring TCR-facing central residues
    - Prefer >= min_hydrophobic hydrophobic residues (scaled down for smaller sets)
  """
    cfg = DEFAULT_HOTSPOT_CONFIG
    min_hotspots = min_hotspots if min_hotspots is not None else cfg["min_hotspots"]
    max_hotspots = max_hotspots if max_hotspots is not None else cfg["max_hotspots"]
    min_hydrophobic = min_hydrophobic if min_hydrophobic is not None else cfg["min_hydrophobic"]

    peptide_length = len(residue_scores)
    preferred = {r.position_index + 1 for r in residue_scores if r.tcr_exposure_prior >= 0.8}
    if not preferred:
        preferred = {i + 1 for i in range(3, peptide_length)}

    anchor_filter = AnchorFilter(allele)
    candidates: list[tuple[float, ResidueScore]] = []
    for r in residue_scores:
        position_1based = r.position_index + 1
        if not _position_eligible(position_1based, r.aa, peptide_length, allele):
            continue
        chem = RESIDUE_CHEMICAL_SCORE.get(r.aa, 0.0) / 10.0
        combined = 0.85 * r.score + 0.15 * chem
        combined *= _anchor_rank_multiplier(r, peptide_length, allele, anchor_filter)
        candidates.append((combined, r))

    if not candidates:
        raise ValueError("No eligible hotspot candidates after biological filtering")

    n_candidates = len(candidates)
    effective_min = min(min_hotspots, n_candidates)
    effective_max = min(max_hotspots, n_candidates)
    target = effective_max

    primary = [c for c in candidates if (c[1].position_index + 1) in preferred]
    other = [c for c in candidates if c not in primary]
    pool = primary if len(primary) >= effective_min else primary + other

    selected: list[ResidueScore] = []
    selected_positions: set[int] = set()

    for _, r in sorted(pool, key=lambda x: (x[1].position_index + 1 not in preferred, -x[0], x[1].position_index)):
        if len(selected) >= target:
            break
        if r.position_index in selected_positions:
            continue
        selected.append(r)
        selected_positions.add(r.position_index)

    if len(selected) < effective_min:
        for _, r in candidates:
            if len(selected) >= effective_min:
                break
            if r.position_index not in selected_positions:
                selected.append(r)
                selected_positions.add(r.position_index)

    required_hydrophobic = _effective_hydrophobic_requirement(len(selected), min_hydrophobic)
    aas = "".join(r.aa for r in selected)

    if _count_hydrophobic(aas) < required_hydrophobic:
        for _, r in candidates:
            if r.position_index in selected_positions:
                continue
            if r.aa not in HYDROPHOBIC_FOR_INTERFACE:
                continue
            if len(selected) >= effective_max:
                replace_idx = next(
                    (i for i, s in enumerate(selected) if s.aa not in HYDROPHOBIC_FOR_INTERFACE),
                    None,
                )
                if replace_idx is None:
                    continue
                selected_positions.discard(selected[replace_idx].position_index)
                selected[replace_idx] = r
                selected_positions.add(r.position_index)
            else:
                selected.append(r)
                selected_positions.add(r.position_index)
            aas = "".join(s.aa for s in selected)
            if _count_hydrophobic(aas) >= required_hydrophobic:
                break

    if _count_hydrophobic("".join(r.aa for r in selected)) < required_hydrophobic:
        logger.warning(
            "Hydrophobic requirement partially met: %d/%d in %d hotspots",
            _count_hydrophobic("".join(r.aa for r in selected)),
            required_hydrophobic,
            len(selected),
        )

    selected.sort(key=lambda r: r.position_index)
    return selected
