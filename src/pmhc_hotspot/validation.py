"""Structure validation before scoring."""

from __future__ import annotations

from dataclasses import dataclass, field

from Bio.PDB.Structure import Structure

from pmhc_hotspot.io import chain_ca_residues, get_chain, infer_peptide_hla_chains, residue_aa1


@dataclass
class ValidationReport:
    """Non-fatal warnings and fatal errors from structure validation."""

    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_fatal(self) -> None:
        if self.errors:
            raise ValueError("; ".join(self.errors))


class StructureValidator:
    """Validate pMHC structures for hotspot scoring."""

    MIN_PEPTIDE_LENGTH = 8
    MAX_PEPTIDE_LENGTH = 15
    STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")

    def validate(
        self,
        structure: Structure,
        peptide_chain: str | None = None,
        hla_chain: str | None = None,
    ) -> ValidationReport:
        report = ValidationReport()

        try:
            pep_id, hla_ids = infer_peptide_hla_chains(structure, peptide_chain, hla_chain)
        except ValueError as exc:
            report.errors.append(str(exc))
            return report

        pep_chain = get_chain(structure, pep_id)
        pep_residues = chain_ca_residues(pep_chain)
        pep_len = len(pep_residues)

        if pep_len < self.MIN_PEPTIDE_LENGTH:
            report.errors.append(
                f"Peptide chain {pep_id} has {pep_len} residues; "
                f"minimum supported length is {self.MIN_PEPTIDE_LENGTH}"
            )
        elif pep_len > self.MAX_PEPTIDE_LENGTH:
            report.warnings.append(
                f"Peptide length {pep_len} exceeds typical MHC-I range; "
                "anchor rules may be less reliable"
            )

        nonstandard = []
        missing_backbone = []
        altloc_residues = []

        for residue in pep_residues:
            aa = residue_aa1(residue)
            if aa == "X":
                nonstandard.append(f"{pep_id}{residue.id[1]}")
            elif aa not in self.STANDARD_AA:
                nonstandard.append(f"{pep_id}{residue.id[1]}({aa})")

            if not all(atom in residue for atom in ("N", "CA", "C")):
                missing_backbone.append(f"{pep_id}{residue.id[1]}")

            atoms = list(residue.get_atoms())
            altlocs = {a.altloc for a in atoms if a.altloc not in (" ", "A")}
            if altlocs:
                altloc_residues.append(f"{pep_id}{residue.id[1]}")

        if nonstandard:
            report.warnings.append(
                f"Non-standard peptide residues (scored with reduced confidence): "
                f"{', '.join(nonstandard[:10])}"
            )
        if missing_backbone:
            report.warnings.append(
                f"Missing backbone atoms on peptide residues: {', '.join(missing_backbone[:10])}"
            )
        if altloc_residues:
            report.warnings.append(
                f"Alternate locations detected; using first altloc only: "
                f"{', '.join(altloc_residues[:10])}"
            )

        if len(hla_ids) > 1:
            report.warnings.append(
                f"Multiple MHC chains detected ({', '.join(hla_ids)}); "
                "contact features aggregate across all MHC chains"
            )

        return report
