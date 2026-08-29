import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


TEMPLATES = [
    "templates/common/status.md",
    "templates/common/gate-report.md",
    "templates/common/acceptance-report.md",
    "templates/common/change-record.md",
    "templates/common/release-record.md",
    "templates/level1/project-brief.md",
    "templates/level1/architecture.md",
    "templates/level1/pending-verification.md",
    "templates/level1/progress-record.md",
    "templates/level2/project-map.md",
    "templates/level2/change-proposal.md",
    "templates/level2/requirements.md",
    "templates/level2/decision-record.md",
    "templates/level2/operations-readiness.md",
    "templates/level2/pending-verification.md",
    "templates/level2/idea-review.md",
    "templates/level2/prd.md",
    "templates/level2/demo.md",
    "templates/level2/tech-spec.md",
    "templates/level2/task.md",
    "templates/level2/deploy-readiness.md",
    "templates/level2/rollback-plan.md",
    "templates/level3/project-map.md",
    "templates/level3/change-proposal.md",
    "templates/level3/regression-report.md",
    "templates/level3/handoff.md",
    "templates/level4/requirements-analysis.md",
]


class TemplateTests(unittest.TestCase):
    def test_templates_exist_and_are_complete(self):
        forbidden = ("TO" + "DO", "T" + "BD")
        for relative in TEMPLATES:
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# "), relative)
            for marker in forbidden:
                self.assertNotIn(marker, text, relative)
            for shared in ["状态", "负责人", "关联 Gate", "最后更新时间"]:
                self.assertIn(shared, text, f"{relative}: {shared}")

    def test_required_sections(self):
        required_sections = {
            "templates/level1/project-brief.md": ["目标用户", "核心路径", "本次不做", "验收标准"],
            "templates/level2/requirements.md": ["目标用户", "范围", "验收标准", "待确认"],
            "templates/level2/demo.md": ["假设", "不做", "验证", "结论"],
            "templates/level2/operations-readiness.md": ["备份", "回滚", "监控", "运营责任"],
            "templates/level3/change-proposal.md": ["当前行为", "期望行为", "影响范围", "回归范围"],
            "templates/level3/regression-report.md": ["基线", "失败复现", "受影响回归", "Review"],
            "templates/level4/requirements-analysis.md": ["机会与问题", "MVP", "方案比较", "不做"],
            "templates/common/gate-report.md": ["已确认事实", "验证证据", "风险", "推荐决策", "等待批准"],
        }
        for relative, sections in required_sections.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for section in sections:
                self.assertIn(section, text, f"{relative}: {section}")

    def test_personal_project_memory_templates_cover_handoff_and_history(self):
        required = {
            "templates/level1/architecture.md": ["模块", "调用关系", "数据", "构建与交付"],
            "templates/level1/progress-record.md": [
                "目标",
                "涉及文件",
                "行为变化",
                "验证",
                "兼容影响",
            ],
            "templates/common/change-record.md": ["范围", "不做", "旧行为", "新行为", "验证"],
            "templates/common/release-record.md": [
                "版本",
                "提交",
                "变更",
                "验证",
                "已知限制",
            ],
        }
        for relative, sections in required.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for section in sections:
                self.assertIn(section, text, f"{relative}: {section}")


if __name__ == "__main__":
    unittest.main()
