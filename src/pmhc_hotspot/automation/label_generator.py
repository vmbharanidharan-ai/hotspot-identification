"""Vectorized TCR–peptide contact labeling (Phase 0.2)."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from pmhc_hotspot.benchmark.contact_labels import (
    CONTACT_MODES,
    ContactMode,
    residue_is_contact,
)
from pmhc_hotspot.benchmark.manifest import BenchmarkEntry
from pmhc_hotspot.features.positioning import PeptideResidueMap
from pmhc_hotspot.features.spatial import heavy_atoms, min_inter_atomic_distance, peptide_tcr_contact_pairs
from pmhc_hotspot.io import StructureLoader, chain_ca_residues, get_chain, infer_peptide_hla_chains

logger = logging.getLogger(__name__)


@dataclass
class ResidueContactLabel:
    position: str
    position_index: int
    is_tcr_contact: bool
    contact_count: int
    closest_tcr_distance: Optional[float]
    contact_entropy: float
    modes: Dict[str, bool]


class ContactLabelGenerator:
    """Compute peptide residue contact labels with optional contact entropy."""

    def __init__(self, contact_mode: ContactMode = "standard"):
        if contact_mode not in CONTACT_MODES:
            raise ValueError(f"contact_mode must be one of {CONTACT_MODES}")
        self.contact_mode = contact_mode

    def label_structure(
        self,
        pdb_path: Path | str,
        *,
        peptide_chain: str | None = None,
        hla_chain: str | None = None,
        tcr_chains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        structure = StructureLoader().load(pdb_path)
        return self.label_structure_object(
            structure,
            pdb_id=Path(pdb_path).stem.upper(),
            peptide_chain=peptide_chain,
            hla_chain=hla_chain,
            tcr_chains=tcr_chains,
        )

    def label_structure_object(
        self,
        structure,
        *,
        pdb_id: str,
        peptide_chain: str | None = None,
        hla_chain: str | None = None,
        tcr_chains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        pep_id, hla_ids = infer_peptide_hla_chains(structure, peptide_chain, hla_chain)
        pep_chain = get_chain(structure, pep_id)
        prm = PeptideResidueMap(pep_chain)

        if tcr_chains is None:
            tcr_chains = []
        if not tcr_chains:
            known = {pep_id, *hla_ids}
            model = structure[0]
            tcr_chains = [
                chain.id
                for chain in model
                if chain.id not in known and len(chain_ca_residues(chain)) >= 80
            ]

        tcr_atoms: list = []
        for chain_id in tcr_chains:
            try:
                tcr_atoms.extend(heavy_atoms(chain_ca_residues(get_chain(structure, chain_id))))
            except ValueError:
                logger.warning("Missing TCR chain %s in %s", chain_id, pdb_path)

        residues: dict[str, dict[str, Any]] = {}
        for i, residue in enumerate(prm.residues):
            pairs = peptide_tcr_contact_pairs(residue, tcr_atoms, max_distance=5.0)
            contact_count = len({round(d, 2) for d, _, _ in pairs})
            closest = min((d for d, _, _ in pairs), default=float("inf"))
            entropy = self._contact_entropy(pairs, len(tcr_atoms))
            modes = {mode: residue_is_contact(pairs, mode) for mode in CONTACT_MODES}  # type: ignore[arg-type]
            position = prm.position_label(i)
            residues[position] = asdict(
                ResidueContactLabel(
                    position=position,
                    position_index=i,
                    is_tcr_contact=modes[self.contact_mode],
                    contact_count=contact_count,
                    closest_tcr_distance=closest if closest != float("inf") else None,
                    contact_entropy=entropy,
                    modes=modes,
                )
            )

        return {
            "pdb_id": pdb_id,
            "peptide_chain": pep_id,
            "hla_chains": hla_ids,
            "tcr_chains": list(tcr_chains),
            "contact_mode": self.contact_mode,
            "residues": residues,
            "n_tcr_atoms": len(tcr_atoms),
        }

    def label_entry(self, entry: BenchmarkEntry, pdb_path: Path | str) -> Dict[str, Any]:
        return self.label_structure(
            pdb_path,
            peptide_chain=entry.peptide_chain,
            hla_chain=entry.hla_chain,
            tcr_chains=list(entry.tcr_chains),
        )

    @staticmethod
    def _contact_entropy(pairs: list, n_tcr_atoms: int) -> float:
        if not pairs or n_tcr_atoms == 0:
            return 0.0
        frac = min(1.0, len(pairs) / max(n_tcr_atoms, 1))
        if frac <= 0.0 or frac >= 1.0:
            return 0.0
        return float(-(frac * np.log(frac) + (1 - frac) * np.log(1 - frac)))


def _label_worker(args: tuple) -> tuple[str, dict | str]:
    pdb_path, kwargs, out_dir = args
    pdb_id = Path(pdb_path).stem.upper()
    try:
        gen = ContactLabelGenerator(contact_mode=kwargs.get("contact_mode", "standard"))
        payload = gen.label_structure(pdb_path, **{k: v for k, v in kwargs.items() if k != "contact_mode"})
        out_path = Path(out_dir) / f"labels_{pdb_id}.json"
        out_path.write_text(json.dumps(payload, indent=2))
        return pdb_id, payload
    except Exception as exc:
        return pdb_id, str(exc)


def batch_label_all_pdbs(
    pdb_dir: Path | str,
    crawler_results: Path | str | None = None,
    output_dir: Path | str = "data/pdb/labels",
    *,
    contact_mode: ContactMode = "standard",
    n_workers: int = 4,
    pdb_ids: Optional[List[str]] = None,
) -> dict:
    """Parallel contact labeling for all PDBs in a directory."""
    pdb_dir = Path(pdb_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if pdb_ids is None:
        if crawler_results and Path(crawler_results).exists():
            data = json.loads(Path(crawler_results).read_text())
            pdb_ids = [e["pdb_id"] for e in data.get("entries", []) if e.get("passed_qc", True)]
        else:
            pdb_ids = [p.stem.upper() for p in pdb_dir.glob("*.pdb")]

    kwargs = {"contact_mode": contact_mode}
    tasks = [(str(pdb_dir / f"{pid}.pdb"), kwargs, str(out_dir)) for pid in pdb_ids]
    summary = {"labeled": [], "skipped": [], "contact_entropy_mean": 0.0}
    entropies: list[float] = []
    if n_workers <= 1:
        results = [_label_worker(t) for t in tasks]
    else:
        results = []
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = [pool.submit(_label_worker, t) for t in tasks]
            for fut in as_completed(futures):
                results.append(fut.result())

    for pdb_id, payload in results:
        if isinstance(payload, str):
            summary["skipped"].append({"pdb_id": pdb_id, "error": payload})
        else:
            summary["labeled"].append(pdb_id)
            for row in payload.get("residues", {}).values():
                entropies.append(float(row.get("contact_entropy", 0.0)))

    if entropies:
        summary["contact_entropy_mean"] = float(np.mean(entropies))
    summary_path = out_dir / "label_batch_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    return summary
