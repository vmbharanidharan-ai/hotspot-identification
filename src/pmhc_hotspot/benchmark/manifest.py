"""Benchmark manifest loading for TCR-bound pMHC structures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class BenchmarkEntry:
    """One structure in the benchmark manifest."""

    pdb_id: str
    allele: str | None
    peptide_chain: str | None = None
    hla_chain: str | None = None
    tcr_chains: tuple[str, ...] = ()
    pdb_path: str | None = None
    notes: str = ""

    @property
    def resolved_pdb_path(self) -> str:
        if self.pdb_path:
            return self.pdb_path
        return str(Path("data/pdb") / f"{self.pdb_id.upper()}.pdb")


class BenchmarkManifest:
    """Iterable manifest of benchmark structures."""

    def __init__(self, manifest_path: str | Path):
        path = Path(manifest_path)
        if not path.exists():
            raise FileNotFoundError(f"Benchmark manifest not found: {path}")
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        self.path = path
        self.entries: list[BenchmarkEntry] = []
        for row in data.get("structures", []):
            tcr = row.get("tcr_chains") or []
            self.entries.append(
                BenchmarkEntry(
                    pdb_id=str(row["pdb_id"]).upper(),
                    allele=row.get("allele"),
                    peptide_chain=row.get("peptide_chain"),
                    hla_chain=row.get("hla_chain"),
                    tcr_chains=tuple(tcr),
                    pdb_path=row.get("pdb_path"),
                    notes=row.get("notes", ""),
                )
            )
        if not self.entries:
            raise ValueError(f"No structures listed in manifest: {path}")

    def __iter__(self):
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    @classmethod
    def default(cls) -> "BenchmarkManifest":
        bundled = Path(__file__).parent / "tcr_pmhc_manifest.yaml"
        return cls(bundled)

    @classmethod
    def resolve(cls, manifest_path: str | Path | None = None) -> "BenchmarkManifest":
        """
        Load the bundled manifest when path is None; otherwise resolve a user path.

        Relative paths are resolved against the current working directory. If not
        found, ``tcr_pmhc_manifest.yaml`` is also checked next to this module
        (supports ``--manifest tcr_pmhc_manifest.yaml`` from any cwd).
        """
        if manifest_path is None:
            return cls.default()

        path = Path(manifest_path)
        if path.is_file():
            return cls(path)

        by_name = Path(__file__).parent / path.name
        if by_name.is_file():
            return cls(by_name)

        raise FileNotFoundError(
            f"Benchmark manifest not found: {path} (cwd={Path.cwd()}). "
            "Omit --manifest to use the bundled default, cd to the repo root, "
            "or pass an absolute path."
        )
