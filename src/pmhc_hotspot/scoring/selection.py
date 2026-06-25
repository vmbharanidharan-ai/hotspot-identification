"""Final RFdiffusion hotspot selection with biological constraints."""

from __future__ import annotations

from pmhc_hotspot.constants import (
    DEFAULT_HOTSPOT_CONFIG,
    HYDROPHOBIC_FOR_INTERFACE,
    RESIDUE_CHEMICAL_SCORE,
    SKIP_ALWAYS,
)
from pmhc_hotspot.features.allele_rules import get_anchor_positions
from pmhc_hotspot.types import ResidueScore


def _count_hydrophobic(amino_acids: str) -> int:
    return sum(1 for aa in amino_acids if aa in HYDROPHOBIC_FOR_INTERFACE)


def _position_eligible(
    position_1based: int,
    aa: str,
    peptide_length: int,
    allele: str | None,
    *,
    allow_n_terminal_small: bool = False,
) -> bool:
    if position_1based in get_anchor_positions(allele, peptide_length):
        return False
    if aa in SKIP_ALWAYS:
        return False
    if position_1based == 1 and aa in {"A", "G"} and not allow_n_terminal_small:
        return False
    return True


def select_rfdiffusion_hotspots(
    residue_scores: list[ResidueScore],
    *,
    allele: str | None = None,
    min_hotspots: int | None = None,
    max_hotspots: int | None = None,
    min_hydrophobic: int | None = None,
) -> list[ResidueScore]:
    """
    Select 5–6 RFdiffusion hotspots with biological design constraints.

    Rules (from pMHC binder design literature and RFdiffusion PPI practice):
    - Skip MHC-I anchor positions (allele-aware)
    - Skip Pro/Gly; skip N-terminal Ala/Gly (flexible, low contact area)
    - Prefer high-scoring TCR-facing central residues
    - Require >= min_hydrophobic hydrophobic residues in final set
    """
    cfg = DEFAULT_HOTSPOT_CONFIG
    min_hotspots = min_hotspots if min_hotspots is not None else cfg["min_hotspots"]
    max_hotspots = max_hotspots if max_hotspots is not None else cfg["max_hotspots"]
    min_hydrophobic = min_hydrophobic if min_hydrophobic is not None else cfg["min_hydrophobic"]

    peptide_length = len(residue_scores)
    preferred = {r.position_index + 1 for r in residue_scores if r.tcr_exposure_prior >= 0.8}
    if not preferred:
        preferred = {i + 1 for i in range(3, peptide_length)}

    candidates: list[tuple[float, ResidueScore]] = []
    for r in residue_scores:
        if not _position_eligible(r.position_index + 1, r.aa, peptide_length, allele):
            continue
        chem = RESIDUE_CHEMICAL_SCORE.get(r.aa, 0.0) / 10.0
        combined = 0.85 * r.score + 0.15 * chem
        candidates.append((combined, r))

    if not candidates:
        raise ValueError("No eligible hotspot candidates after biological filtering")

    candidates.sort(key=lambda x: (-x[0], x[1].position_index))
    primary = [c for c in candidates if (c[1].position_index + 1) in preferred]
    other = [c for c in candidates if c not in primary]

    if len(primary) >= min_hotspots:
        pool = primary
        target = min(len(primary), max_hotspots)
        target = max(target, min_hotspots)
        if len(primary) == min_hotspots:
            target = min_hotspots
    else:
        pool = primary + other
        target = min_hotspots

    selected: list[ResidueScore] = []
    selected_positions: set[int] = set()

    for _, r in sorted(pool, key=lambda x: (x[1].position_index + 1 not in preferred, -x[0], x[1].position_index)):
        if len(selected) >= target:
            break
        if r.position_index in selected_positions:
            continue
        selected.append(r)
        selected_positions.add(r.position_index)

    if len(selected) < min_hotspots:
        for _, r in candidates:
            if len(selected) >= min_hotspots:
                break
            if r.position_index not in selected_positions:
                selected.append(r)
                selected_positions.add(r.position_index)

    selected.sort(key=lambda r: r.position_index)
    aas = "".join(r.aa for r in selected)

    if _count_hydrophobic(aas) < min_hydrophobic:
        for _, r in candidates:
            if r.position_index in selected_positions:
                continue
            if r.aa not in HYDROPHOBIC_FOR_INTERFACE:
                continue
            if len(selected) >= max_hotspots:
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
            if _count_hydrophobic(aas) >= min_hydrophobic:
                break

    if len(selected) < min_hotspots:
        raise ValueError(
            f"Only {len(selected)} eligible hotspots; need {min_hotspots}"
        )
    if _count_hydrophobic("".join(r.aa for r in selected)) < min_hydrophobic:
        raise ValueError(
            f"Could not satisfy hydrophobic requirement (>={min_hydrophobic})"
        )

    selected.sort(key=lambda r: r.position_index)
    return selected
