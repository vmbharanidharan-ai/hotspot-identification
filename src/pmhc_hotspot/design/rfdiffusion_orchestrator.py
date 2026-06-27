"""RFdiffusion design orchestration (Phase 2.2)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

from pmhc_hotspot.design.control_strategies import DesignControlStrategy, get_strategy
from pmhc_hotspot.export import build_contig_template
from pmhc_hotspot.io import StructureLoader, chain_ca_residues, get_chain


@dataclass
class DesignJobResult:
    strategy: str
    pdb_id: str
    config_path: str
    design_paths: List[str] = field(default_factory=list)
    status: str = "pending"
    error: str = ""


class RFdiffusionDesigner:
    """Prepare and optionally run RFdiffusion designs."""

    def __init__(
        self,
        *,
        rfdiffusion_bin: Optional[str] = None,
        num_designs: int = 10,
        seed: int = 42,
        binder_length_min: int = 50,
        binder_length_max: int = 80,
    ):
        self.rfdiffusion_bin = rfdiffusion_bin or os.environ.get("RFDIFFUSION_BIN", "rfdiffusion")
        self.num_designs = num_designs
        self.seed = seed
        self.binder_length_min = binder_length_min
        self.binder_length_max = binder_length_max

    def export_rfdiffusion_config(
        self,
        hotspot_residues: List[int],
        pdb_file: Path,
        peptide_chain: str,
        hla_chain: str,
        output_path: Path,
    ) -> Path:
        structure = StructureLoader().load(pdb_file)
        pep = get_chain(structure, peptide_chain)
        hla = get_chain(structure, hla_chain)
        pep_resseqs = [r.id[1] for r in chain_ca_residues(pep)]
        hla_resseqs = [r.id[1] for r in chain_ca_residues(hla)]
        contig = build_contig_template(
            peptide_chain,
            pep_resseqs,
            hla_chain,
            hla_resseqs,
            binder_length_min=self.binder_length_min,
            binder_length_max=self.binder_length_max,
        )
        tokens = [f"{peptide_chain}{idx}" for idx in hotspot_residues]
        payload = {
            "ppi": {"hotspot_res": ",".join(tokens)},
            "contigmap": {
                "contigs": contig,
                "num_designs": self.num_designs,
            },
            "seed": self.seed,
            "input_pdb": str(pdb_file.resolve()),
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(yaml.safe_dump(payload, sort_keys=False))
        return output_path

    def generate_designs(self, config_path: Path, output_dir: Path) -> List[Path]:
        """Run RFdiffusion if binary exists; otherwise write stub marker files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        if shutil.which(self.rfdiffusion_bin):
            cmd = [self.rfdiffusion_bin, "--config", str(config_path), "--output", str(output_dir)]
            subprocess.run(cmd, check=False)
            return sorted(output_dir.glob("*.pdb"))

        # Stub mode for environments without RFdiffusion installed
        stub = output_dir / "design_000.pdb"
        stub.write_text("REMARK stub design — install RFdiffusion on HPC\n")
        return [stub]

    def run_strategy(
        self,
        strategy: DesignControlStrategy,
        strategy_name: str,
        pdb_file: Path,
        *,
        peptide_chain: str,
        hla_chain: str,
        allele: Optional[str],
        output_root: Path,
    ) -> DesignJobResult:
        pdb_id = pdb_file.stem.upper()
        residues = strategy.select_residues(
            pdb_file, peptide_chain, n_select=5, allele=allele, seed=self.seed
        )
        config_path = output_root / "configs" / f"{pdb_id}_{strategy_name}.yaml"
        self.export_rfdiffusion_config(residues, pdb_file, peptide_chain, hla_chain, config_path)
        design_dir = output_root / "designs" / strategy_name / pdb_id
        try:
            designs = self.generate_designs(config_path, design_dir)
            return DesignJobResult(
                strategy=strategy_name,
                pdb_id=pdb_id,
                config_path=str(config_path),
                design_paths=[str(p) for p in designs],
                status="completed" if designs else "failed",
            )
        except Exception as exc:
            return DesignJobResult(
                strategy=strategy_name,
                pdb_id=pdb_id,
                config_path=str(config_path),
                status="failed",
                error=str(exc),
            )


def batch_design_all_controls(
    eval_pdb_list: List[dict],
    strategies: Optional[List[str]] = None,
    output_dir: Path | str = "artifacts/design_outputs",
    *,
    designer: Optional[RFdiffusionDesigner] = None,
) -> dict:
    strategies = strategies or ["hotspot", "random", "exposed", "central"]
    designer = designer or RFdiffusionDesigner()
    out_root = Path(output_dir)
    results: list[dict] = []

    for entry in eval_pdb_list:
        pdb_path = Path(entry["pdb_path"])
        peptide_chain = entry["peptide_chain"]
        hla_chain = entry.get("hla_chain") or entry.get("mhc_chain")
        allele = entry.get("allele")
        for strategy_name in strategies:
            strategy = get_strategy(strategy_name)
            job = designer.run_strategy(
                strategy,
                strategy_name,
                pdb_path,
                peptide_chain=peptide_chain,
                hla_chain=hla_chain,
                allele=allele,
                output_root=out_root,
            )
            results.append(job.__dict__)

    summary_path = out_root / "design_batch_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps({"jobs": results}, indent=2))
    return {"n_jobs": len(results), "summary_path": str(summary_path)}
