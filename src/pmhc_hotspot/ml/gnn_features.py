"""GNN node/edge features with structure + sequence fusion (Phase 3.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from pmhc_hotspot.constants import RESIDUE_CHEMICAL_SCORE, THREE_TO_ONE
from pmhc_hotspot.features.allele_rules import get_anchor_positions
from pmhc_hotspot.features.positioning import PeptideResidueMap
from pmhc_hotspot.features.spatial import heavy_atoms, min_inter_atomic_distance
from pmhc_hotspot.io import StructureLoader, chain_ca_residues, get_chain, infer_peptide_hla_chains, residue_aa1

# Kyte-Doolittle hydrophobicity (simplified)
HYDROPHOBICITY = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5, "G": -0.4,
    "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8, "P": -1.6, "S": -0.8,
    "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}
CHARGE = {"R": 1, "K": 1, "H": 0.1, "D": -1, "E": -1}


def compute_peptide_node_features(
    pdb_file: Path | str,
    peptide_chain: str,
    allele: str | None,
    *,
    mhc_binding_scores: Dict[int, float] | None = None,
) -> List[Dict[str, float]]:
    structure = StructureLoader().load(pdb_file)
    pep = get_chain(structure, peptide_chain)
    _, hla_ids = infer_peptide_hla_chains(structure, peptide_chain, None)
    hla_atoms = []
    for hid in hla_ids:
        hla_atoms.extend(heavy_atoms(chain_ca_residues(get_chain(structure, hid))))
    prm = PeptideResidueMap(pep)
    anchors = set(get_anchor_positions(allele, prm.length))
    mhc_binding_scores = mhc_binding_scores or {}

    rows: list[dict[str, float]] = []
    for i, residue in enumerate(prm.residues):
        aa = residue_aa1(residue)
        ca_atoms = [a for a in residue if a.name == "CA"]
        ca = ca_atoms[0] if ca_atoms else None
        mhc_dist = min_inter_atomic_distance(heavy_atoms(residue), hla_atoms) if hla_atoms else 0.0
        rows.append(
            {
                "relative_sasa": 0.5,
                "burial_depth": max(0.0, 10.0 - mhc_dist),
                "mean_distance_to_mhc": mhc_dist,
                "contact_count_mhc": float(len(hla_atoms) > 0),
                "residue_hydrophobicity": HYDROPHOBICITY.get(aa, 0.0),
                "residue_charge": CHARGE.get(aa, 0.0),
                "position_in_peptide": i / max(prm.length - 1, 1),
                "is_anchor_by_allele": float((i + 1) in anchors),
                "chemical_score": RESIDUE_CHEMICAL_SCORE.get(aa, 0.0) / 10.0,
                "mhc_binding_score": float(mhc_binding_scores.get(i, 0.5)),
                "mhc_binding_percentile": float(mhc_binding_scores.get(i, 0.5)),
            }
        )
    return rows


def compute_peptide_edge_index(
    n_residues: int,
    ca_coords: np.ndarray,
    *,
    distance_threshold: float = 8.0,
) -> Tuple[np.ndarray, np.ndarray]:
    src: list[int] = []
    dst: list[int] = []
    attrs: list[list[float]] = []
    for i in range(n_residues):
        for j in range(i + 1, n_residues):
            dist = float(np.linalg.norm(ca_coords[i] - ca_coords[j]))
            if dist <= distance_threshold or abs(i - j) == 1:
                src.extend([i, j])
                dst.extend([j, i])
                weight = 1.0 if abs(i - j) == 1 else max(0.1, 1.0 - dist / distance_threshold)
                attrs.append([dist, weight])
                attrs.append([dist, weight])
    if not src:
        loops = np.arange(n_residues)
        edge_index = np.stack([loops, loops])
        return edge_index, np.zeros((n_residues, 2), dtype=np.float32)
    return np.asarray([src, dst], dtype=np.int64), np.asarray(attrs, dtype=np.float32)


def assemble_graph_inputs(
    pdb_file: Path | str,
    peptide_chain: str,
    allele: str | None,
    labels: List[int],
):
    """Assemble PyG Data object when torch_geometric is available."""
    torch, Data = _require_pyg()
    structure = StructureLoader().load(pdb_file)
    pep = get_chain(structure, peptide_chain)
    prm = PeptideResidueMap(pep)
    node_feats = compute_peptide_node_features(pdb_file, peptide_chain, allele)
    ca_coords = np.array([r["CA"].coord for r in prm.residues if "CA" in r], dtype=np.float32)
    edge_index, edge_attr = compute_peptide_edge_index(len(prm.residues), ca_coords)
    x = torch.tensor([[v for v in row.values()] for row in node_feats], dtype=torch.float32)
    y = torch.tensor(labels, dtype=torch.float32)
    return Data(x=x, edge_index=torch.tensor(edge_index, dtype=torch.long), edge_attr=torch.tensor(edge_attr, dtype=torch.float32), y=y)


def _require_pyg():
    try:
        import torch
        from torch_geometric.data import Data
    except ImportError as exc:
        raise ImportError('Install GNN stack: pip install -e ".[gnn]" torch-geometric') from exc
    return torch, Data
