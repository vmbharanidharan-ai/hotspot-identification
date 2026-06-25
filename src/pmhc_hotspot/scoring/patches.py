"""Contiguous hotspot patch selection."""

from __future__ import annotations

from pmhc_hotspot.types import HotspotPatch, ResidueScore


class PatchSelector:
    """
    Select contiguous peptide surface patches from scored residues.

    RFdiffusion PPI design benefits from spatially coherent targets
    rather than isolated single residues.
    """

    def __init__(
        self,
        min_patch_size: int = 2,
        max_patches: int = 3,
        expansion_threshold: float = 0.5,
    ):
        self.min_patch_size = min_patch_size
        self.max_patches = max_patches
        self.expansion_threshold = expansion_threshold

    def select(self, residue_scores: list[ResidueScore]) -> list[HotspotPatch]:
        if not residue_scores:
            return []

        by_index = {r.position_index: r for r in residue_scores}
        ordered = sorted(residue_scores, key=lambda r: r.score, reverse=True)
        used_indices: set[int] = set()
        patches: list[HotspotPatch] = []

        for seed in ordered:
            if len(patches) >= self.max_patches:
                break
            if seed.position_index in used_indices:
                continue

            patch_residues = [seed]
            used_indices.add(seed.position_index)

            # Expand left
            idx = seed.position_index - 1
            while idx in by_index and idx not in used_indices:
                neighbor = by_index[idx]
                if neighbor.score >= self.expansion_threshold * seed.score:
                    patch_residues.insert(0, neighbor)
                    used_indices.add(idx)
                    idx -= 1
                else:
                    break

            # Expand right
            idx = seed.position_index + 1
            while idx in by_index and idx not in used_indices:
                neighbor = by_index[idx]
                if neighbor.score >= self.expansion_threshold * seed.score:
                    patch_residues.append(neighbor)
                    used_indices.add(idx)
                    idx += 1
                else:
                    break

            if len(patch_residues) >= self.min_patch_size:
                patch_residues.sort(key=lambda r: r.position_index)
                positions = [r.position for r in patch_residues]
                mean_score = sum(r.score for r in patch_residues) / len(patch_residues)
                contiguity_bonus = len(patch_residues) ** 0.5
                patch_score = mean_score * contiguity_bonus / (contiguity_bonus + 1.0)
                patches.append(
                    HotspotPatch(
                        positions=positions,
                        residues=patch_residues,
                        patch_score=patch_score,
                        patch_id=len(patches) + 1,
                    )
                )

        patches.sort(key=lambda p: p.patch_score, reverse=True)
        return patches
