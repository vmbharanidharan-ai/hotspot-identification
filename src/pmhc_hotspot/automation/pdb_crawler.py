"""Automated RCSB PDB discovery and chain inference (Phase 0.1)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from pmhc_hotspot.io import (
    StructureLoader,
    chain_ca_residues,
    chain_residue_count,
    get_model,
    infer_peptide_hla_chains,
    residue_aa1,
)

logger = logging.getLogger(__name__)

RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_DOWNLOAD_URL = "https://files.rcsb.org/download/{pdb_id}.pdb"


@dataclass
class CrawlEntry:
    pdb_id: str
    release_date: Optional[str] = None
    resolution: Optional[float] = None
    url: str = ""
    notes: str = ""
    passed_qc: bool = False


@dataclass
class ChainInference:
    pdb_id: str
    peptide_chain: Optional[str] = None
    mhc_chain: Optional[str] = None
    tcr_chains: List[str] = field(default_factory=list)
    confidence: float = 0.0
    notes: str = ""
    ambiguous: bool = False


class PDBCrawler:
    """Query RCSB PDB for TCR–pMHC structures and download files."""

    def __init__(
        self,
        *,
        cache_dir: Path | str = "data/pdb",
        min_release_year: int = 2015,
        max_resolution: float = 3.5,
        preferred_resolution: float = 2.5,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_release_year = min_release_year
        self.max_resolution = max_resolution
        self.preferred_resolution = preferred_resolution

    def search(
        self,
        query_text: str = "TCR AND pMHC AND (peptide OR immunoglobulin)",
        *,
        rows: int = 500,
    ) -> list[CrawlEntry]:
        """Search RCSB and return metadata entries (no download)."""
        payload = {
            "query": {
                "type": "terminal",
                "service": "full_text",
                "parameters": {"value": query_text},
            },
            "return_type": "entry",
            "request_options": {
                "paginate": {"start": 0, "rows": rows},
                "results_content_type": ["experimental"],
                "sort": [{"sort_by": "rcsb_accession_info.deposit_date", "direction": "desc"}],
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            RCSB_SEARCH_URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning("RCSB search failed: %s", exc)
            return []

        entries: list[CrawlEntry] = []
        for item in data.get("result_set", []):
            pdb_id = str(item.get("identifier", "")).upper()
            if not pdb_id:
                continue
            entries.append(
                CrawlEntry(
                    pdb_id=pdb_id,
                    url=RCSB_DOWNLOAD_URL.format(pdb_id=pdb_id),
                    notes="rcsb_search",
                )
            )
        return entries

    def download(self, pdb_id: str) -> Path:
        pdb_id = pdb_id.upper()
        dest = self.cache_dir / f"{pdb_id}.pdb"
        if dest.exists():
            return dest
        url = RCSB_DOWNLOAD_URL.format(pdb_id=pdb_id)
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                dest.write_bytes(resp.read())
        except urllib.error.URLError as exc:
            raise FileNotFoundError(f"Failed to download {pdb_id}: {exc}") from exc
        return dest

    def crawl(
        self,
        pdb_ids: Optional[List[str]] = None,
        *,
        download: bool = True,
    ) -> list[CrawlEntry]:
        entries = (
            [CrawlEntry(pdb_id=p.upper(), url=RCSB_DOWNLOAD_URL.format(pdb_id=p.upper())) for p in pdb_ids]
            if pdb_ids
            else self.search()
        )
        results: list[CrawlEntry] = []
        for entry in entries:
            try:
                if download:
                    self.download(entry.pdb_id)
                inference = PDBStructureAnalyzer().analyze(self.cache_dir / f"{entry.pdb_id}.pdb")
                entry.passed_qc = inference.confidence >= 0.5 and not inference.ambiguous
                entry.notes = inference.notes
            except Exception as exc:
                entry.notes = f"qc_failed: {exc}"
                entry.passed_qc = False
            results.append(entry)
        return results

    def write_results(self, entries: list[CrawlEntry], output_dir: Path | str = "data/pdb") -> Path:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = out_dir / f"crawl_results_{stamp}.json"
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_entries": len(entries),
            "entries": [asdict(e) for e in entries],
        }
        path.write_text(json.dumps(payload, indent=2))
        return path


class PDBStructureAnalyzer:
    """Infer peptide, MHC, and TCR chains from a structure file."""

    def analyze(self, pdb_path: Path | str) -> ChainInference:
        path = Path(pdb_path)
        structure = StructureLoader().load(path)
        model = get_model(structure)
        lengths = {chain.id: chain_residue_count(chain) for chain in model}
        lengths = {k: v for k, v in lengths.items() if v > 0}
        if not lengths:
            return ChainInference(pdb_id=path.stem.upper(), notes="no_chains", confidence=0.0)

        peptide_candidates = [c for c, n in lengths.items() if 8 <= n <= 15]
        mhc_candidates = [c for c, n in lengths.items() if n >= 150]
        tcr_candidates = [c for c, n in lengths.items() if 80 <= n <= 250 and c not in peptide_candidates]

        try:
            pep, hla_ids = infer_peptide_hla_chains(structure)
        except ValueError:
            pep = peptide_candidates[0] if peptide_candidates else None
            hla_ids = mhc_candidates[:1]

        tcr_chains = [c for c in tcr_candidates if c not in {pep, *hla_ids}]
        if not tcr_chains:
            tcr_chains = [
                c
                for c, n in lengths.items()
                if c not in {pep, *hla_ids} and 70 <= n <= 300
            ][:2]

        ambiguous = len(peptide_candidates) > 1 or len(tcr_candidates) > 3
        confidence = 0.9
        if pep is None or not hla_ids:
            confidence = 0.2
        elif not tcr_chains:
            confidence = 0.5
        if ambiguous:
            confidence *= 0.7

        notes = []
        if ambiguous:
            notes.append("ambiguous_chain_assignment")
        if not tcr_chains:
            notes.append("no_tcr_detected")

        return ChainInference(
            pdb_id=path.stem.upper(),
            peptide_chain=pep,
            mhc_chain=hla_ids[0] if hla_ids else None,
            tcr_chains=tcr_chains,
            confidence=round(confidence, 3),
            notes="; ".join(notes),
            ambiguous=ambiguous,
        )

    def sequence_length(self, pdb_path: Path | str, chain_id: str) -> int:
        structure = StructureLoader().load(pdb_path)
        return chain_residue_count(get_model(structure)[chain_id])

    def peptide_sequence(self, pdb_path: Path | str, chain_id: str) -> str:
        structure = StructureLoader().load(pdb_path)
        chain = get_model(structure)[chain_id]
        return "".join(residue_aa1(r) for r in chain_ca_residues(chain))
