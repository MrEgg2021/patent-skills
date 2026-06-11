import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from docx_parser import ParsedDocument, SectionData  # noqa: E402
from formality_scanner import FormalityScanner  # noqa: E402


def make_section(section_type, paragraphs):
    return SectionData(
        section_type=section_type,
        header_text=section_type,
        paragraphs=paragraphs,
    )


def scan_document(sections):
    parsed = ParsedDocument(
        patent_type="发明",
        invention_name="一种测试装置",
        sections=sections,
    )
    return FormalityScanner(parsed, target_center="安徽").run_all()


def issues_for(result, rule_id):
    return [issue for issue in result.issues if issue["rule_id"] == rule_id]


class FormalityScannerReviewPolicyTest(unittest.TestCase):
    def test_claim_measurement_numbers_do_not_create_c6_final_issue(self):
        result = scan_document({
            "权利要求书": make_section("权利要求书", [
                "1. 一种温控方法，其特征在于，温度为10℃，比例为20%，执行步骤20后输出结果。"
            ])
        })

        self.assertEqual([], issues_for(result, "C-6"))

    def test_claim_bare_reference_number_requires_llm_review(self):
        result = scan_document({
            "权利要求书": make_section("权利要求书", [
                "1. 一种处理装置，其特征在于，包括模块101和控制器。"
            ])
        })

        c6_issues = issues_for(result, "C-6")
        self.assertEqual(1, len(c6_issues))
        self.assertEqual("llm_required", c6_issues[0]["review_policy"])
        self.assertEqual("word_docx", c6_issues[0]["surface"])
        self.assertEqual("medium", c6_issues[0]["confidence"])
        self.assertEqual("101", c6_issues[0]["matched_text"])
        self.assertIn("模块101", c6_issues[0]["context"])
        self.assertEqual(0, result.summary["a_rules_failed"])
        self.assertEqual(1, result.summary["llm_required_count"])

    def test_parenthesized_reference_number_does_not_create_c6_issue(self):
        result = scan_document({
            "权利要求书": make_section("权利要求书", [
                "1. 一种处理装置，其特征在于，包括模块（101）和控制器。"
            ])
        })

        self.assertEqual([], issues_for(result, "C-6"))

    def test_abstract_bare_number_requires_llm_review(self):
        result = scan_document({
            "摘要": make_section("摘要", [
                "本发明公开一种处理装置，包括模块101和控制器，能够提高处理效率。"
            ])
        })

        ab5_issues = issues_for(result, "AB-5")
        self.assertEqual(1, len(ab5_issues))
        self.assertEqual("llm_required", ab5_issues[0]["review_policy"])
        self.assertEqual("101", ab5_issues[0]["matched_text"])
        self.assertEqual(0, result.summary["a_rules_failed"])

    def test_missing_spec_subheading_remains_script_final_must_fix(self):
        result = scan_document({
            "说明书": make_section("说明书", [
                "技术领域",
                "背景技术",
                "发明内容",
                "附图说明",
            ])
        })

        s3_issues = issues_for(result, "S-3")
        self.assertEqual(1, len(s3_issues))
        self.assertEqual("script_final", s3_issues[0]["review_policy"])
        self.assertEqual("must_fix", s3_issues[0]["severity"])
        self.assertIn("具体实施方式", s3_issues[0]["description"])

    def test_numbered_spec_subheading_requires_official_preview_review(self):
        result = scan_document({
            "说明书": make_section("说明书", [
                "1. 技术领域",
                "背景技术",
                "发明内容",
                "附图说明",
                "具体实施方式",
            ])
        })

        s3_issues = issues_for(result, "S-3")
        self.assertEqual(1, len(s3_issues))
        self.assertEqual("official_preview_required", s3_issues[0]["review_policy"])
        self.assertEqual("official_pdf_preview", s3_issues[0]["surface"])
        self.assertEqual("confirm", s3_issues[0]["severity"])
        self.assertIn("1. 技术领域", s3_issues[0]["matched_text"])
        self.assertEqual(0, result.summary["a_rules_failed"])
        self.assertEqual(1, result.summary["official_preview_required_count"])


if __name__ == "__main__":
    unittest.main()
