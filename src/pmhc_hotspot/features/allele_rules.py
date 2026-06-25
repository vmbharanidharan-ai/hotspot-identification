"""Allele-aware MHC-I anchor rules."""

from __future__ import annotations

import re

# Curated MHC-I anchor positions (1-based peptide indices).
# Sources: NetMHCpan motif tables, Rudolph et al. (MHC-I peptide binding),
# and allele-specific structural literature.
#
# Rules use position indices relative to peptide length:
# - N-terminal anchor: position 2 (P2) for most class I alleles
# - C-terminal anchor: last position (PΩ) for 8+ mers
# - Some alleles have secondary anchors at P3 or PΩ-1

ANCHOR_RULES: dict[str, dict] = {
    "HLA-A*02:01": {
        "anchors": [2, -1],
        "suppression": 0.5,
        "notes": "P2 (Leu/Met/Ala) and C-terminal anchor (Leu/Val)",
    },
    "HLA-A*01:01": {
        "anchors": [2, -1],
        "suppression": 0.5,
        "notes": "P2 small/aliphatic; C-terminal Tyr",
    },
    "HLA-A*03:01": {
        "anchors": [2, -1],
        "suppression": 0.5,
        "notes": "P2 basic; C-terminal basic/hydrophobic",
    },
    "HLA-A*24:02": {
        "anchors": [2, -1],
        "suppression": 0.6,
        "notes": "P2 aromatic (Phe/Tyr/Trp); C-terminal hydrophobic",
    },
    "HLA-A*11:01": {
        "anchors": [2, -1],
        "suppression": 0.5,
        "notes": "P2 basic; C-terminal hydrophobic",
    },
    "HLA-B*07:02": {
        "anchors": [2, -1],
        "suppression": 0.5,
        "notes": "P2 Pro; C-terminal hydrophobic",
    },
    "HLA-B*08:01": {
        "anchors": [2, -1],
        "suppression": 0.5,
        "notes": "P2 basic; C-terminal hydrophobic",
    },
    "HLA-B*44:02": {
        "anchors": [2, -1],
        "suppression": 0.5,
        "notes": "P2 Glu/Asp; C-terminal hydrophobic",
    },
    "HLA-B*44:03": {
        "anchors": [2, -1],
        "suppression": 0.5,
        "notes": "P2 Glu/Asp; C-terminal hydrophobic",
    },
    "HLA-C*07:02": {
        "anchors": [2, -1],
        "suppression": 0.5,
        "notes": "P2 hydrophobic; C-terminal hydrophobic",
    },
}

# Generic MHC-I fallback when allele is unknown.
DEFAULT_MHC_I_ANCHORS = [2, -1]
DEFAULT_SUPPRESSION = 0.5


def normalize_allele(allele: str | None) -> str | None:
    """Normalize allele strings to HLA-A*02:01 style."""
    if not allele:
        return None
    s = allele.strip().upper().replace(" ", "")
    if "*" in s:
        return s
    # HLA-A0201, HLA-A02:01 -> HLA-A*02:01
    m = re.match(r"^(HLA-[ABC])(\d{2})[:.]?(\d{2})$", s)
    if m:
        return f"{m.group(1)}*{m.group(2)}:{m.group(3)}"
    m = re.match(r"^(HLA-[ABC])(\d{2})(\d{2})$", s)
    if m:
        return f"{m.group(1)}*{m.group(2)}:{m.group(3)}"
    return s


def resolve_anchor_rule(allele: str | None) -> dict:
    """Look up anchor rule for allele, with normalization."""
    norm = normalize_allele(allele)
    if norm and norm in ANCHOR_RULES:
        return ANCHOR_RULES[norm]
    if norm:
        for key, rule in ANCHOR_RULES.items():
            if key.replace("*", "") == norm.replace("*", ""):
                return rule
    return {
        "anchors": DEFAULT_MHC_I_ANCHORS,
        "suppression": DEFAULT_SUPPRESSION,
        "notes": "Generic MHC-I P2 + C-terminal anchors (allele unknown)",
    }


def get_anchor_positions(allele: str | None, peptide_length: int) -> frozenset[int]:
    """Return 1-based anchor positions for a peptide of given length."""
    rule = resolve_anchor_rule(allele)
    positions: set[int] = set()
    for anchor in rule["anchors"]:
        if anchor == -1:
            if peptide_length >= 8:
                positions.add(peptide_length)
        elif 1 <= anchor <= peptide_length:
            positions.add(anchor)
    return frozenset(positions)


class AnchorFilter:
    """
    Allele-aware anchor suppression.

    Penalty is multiplicative and strongest when the anchor residue is
    both an anchor position AND buried in the HLA groove (high MHC contacts
    or low relative SASA). This reflects pMHC biology: buried anchors are
    poor RFdiffusion targets; exposed anchors may still be penalized mildly.
    """

    def __init__(self, allele: str | None):
        self.allele = normalize_allele(allele)
        self.rule = resolve_anchor_rule(self.allele)

    def is_anchor(self, position_1based: int, peptide_length: int) -> bool:
        return position_1based in get_anchor_positions(self.allele, peptide_length)

    def penalty(
        self,
        position_1based: int,
        peptide_length: int,
        *,
        buried: bool,
        relative_sasa: float,
    ) -> float:
        """
        Return multiplicative penalty factor in [0, 1].

        0 = no penalty; 1 = full suppression (score multiplied by 0).
        """
        if not self.is_anchor(position_1based, peptide_length):
            return 0.0

        suppression = float(self.rule["suppression"])

        if buried:
            return suppression

        # Partial penalty for exposed anchors (still suboptimal design targets)
        if relative_sasa > 0.4:
            return suppression * 0.3
        return suppression * 0.6
