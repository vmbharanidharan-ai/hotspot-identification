"""Per-residue score explanation utilities."""

from __future__ import annotations

from pmhc_hotspot.types import ResidueScore


def format_explanation(residue: ResidueScore) -> str:
    """Human-readable one-line explanation for CLI output."""
    parts = []
    exp = residue.explanation
    ranked = sorted(exp.items(), key=lambda x: abs(x[1]), reverse=True)
    for name, value in ranked[:4]:
        if abs(value) < 1e-4:
            continue
        sign = "+" if value >= 0 else ""
        parts.append(f"{name}:{sign}{value:.2f}")
    flags = []
    if residue.is_anchor:
        flags.append("anchor")
    if residue.is_buried:
        flags.append("buried")
    if not residue.eligible_for_hotspot:
        flags.append("ineligible")
    if flags:
        parts.append(f"[{','.join(flags)}]")
    return ", ".join(parts) if parts else "no dominant component"
