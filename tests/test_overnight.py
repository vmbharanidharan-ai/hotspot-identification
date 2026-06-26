"""Tests for overnight package loop helpers."""

from pmhc_hotspot.automation.overnight import (
    build_agent_prompt,
    compare_eval_reports,
    parse_reviewer_verdict,
    should_attempt_code_patch,
    weak_eval_structures,
)


def test_build_agent_prompt_strips_frontmatter():
    prompt = build_agent_prompt("analyst.md")
    assert "name: analyst" not in prompt
    assert "Analyst" in prompt or "analyst" in prompt.lower()


def test_weak_eval_structures():
    report = {
        "results": [
            {"pdb_id": "A", "skipped": False, "recall_at_k": {5: 0.2}, "peptide_length": 9},
            {"pdb_id": "B", "skipped": False, "recall_at_k": {5: 0.9}, "peptide_length": 9},
        ]
    }
    weak = weak_eval_structures(report, recall_threshold=0.5)
    assert len(weak) == 1
    assert weak[0]["pdb_id"] == "A"


def test_should_attempt_code_patch():
    benchmark = {"summary": {"mean_recall_at_5": 0.72}}
    biology = {"passed": True}
    assert should_attempt_code_patch(benchmark, biology) is True
    benchmark["summary"]["mean_recall_at_5"] = 0.80
    assert should_attempt_code_patch(benchmark, biology) is False


def test_compare_eval_reports_improved():
    baseline = {"summary": {"mean_recall_at_5": 0.72, "mean_buried_anchor_avoidance_at_5": 1.0}}
    current = {"summary": {"mean_recall_at_5": 0.78, "mean_buried_anchor_avoidance_at_5": 1.0}}
    result = compare_eval_reports(current, baseline, target_recall=0.77)
    assert result["package_improved"] is True


def test_parse_reviewer_verdict():
    assert parse_reviewer_verdict("APPROVE\nLooks good.") == "APPROVE"
    assert parse_reviewer_verdict("REJECT: too broad") == "REJECT"
