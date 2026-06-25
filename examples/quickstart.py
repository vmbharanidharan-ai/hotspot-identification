"""Example: score hotspots on a test structure."""

from pathlib import Path

from pmhc_hotspot import HotspotPredictor

EXAMPLE_PDB = Path(__file__).resolve().parents[1] / "tests" / "data" / "minimal_pmhc.pdb"


def main():
    result = HotspotPredictor(allele="HLA-A*02:01").predict(EXAMPLE_PDB)

    print("Peptide:", result.peptide_sequence)
    print("RFdiffusion hotspots:", result.rfdiffusion_hotspot_res)
    print("Contig:", result.contig_template)
    print()
    print(f"{'Pos':<6} {'AA':<4} {'Score':<8} {'Buried':<8} {'Anchor'}")
    for r in sorted(result.residue_scores, key=lambda x: x.position_index):
        print(
            f"{r.position:<6} {r.aa:<4} {r.score:<8.3f} "
            f"{str(r.is_buried):<8} {str(r.is_anchor)}"
        )


if __name__ == "__main__":
    main()
