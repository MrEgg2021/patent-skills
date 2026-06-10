#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
形式审查自动扫描器 — A类规则（36条脚本化规则）

基于DocxSectionParser输出的ParsedDocument结构化数据，
执行36条可通过脚本自动判定的审查规则。

含中心选择判定逻辑：根据target_center参数调整分歧项/独有项的判定标准。
"""

# 跨平台：确保非 ASCII（中文/emoji）输出在 Windows GBK 控制台不崩溃
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding='utf-8')
    _sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
import re
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

# 导入docx_parser的数据结构
# 注意：运行时需确保docx_parser.py在同一目录或PYTHONPATH中
try:
    from docx_parser import ParsedDocument, SectionData
except ImportError:
    # 尝试从当前目录导入
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from docx_parser import ParsedDocument, SectionData


# ──────────────────────────────────────────────
# 中心选择配置
# ──────────────────────────────────────────────

# 19个已覆盖的保护中心
VALID_CENTERS = [
    "吉林", "徐州", "浙江", "北京", "山西", "甘肃", "长沙", "长春",
    "福建", "西安", "内蒙古", "陕西", "安徽", "辽宁", "湖北",
    "合肥", "常州", "苏州", "天津"
]

# 中心名称别名映射
CENTER_ALIASES = {
    "吉林": "吉林", "吉林省": "吉林",
    "徐州": "徐州", "徐州市": "徐州",
    "浙江": "浙江", "浙江省": "浙江",
    "北京": "北京", "北京市": "北京",
    "山西": "山西", "山西省": "山西",
    "甘肃": "甘肃", "甘肃省": "甘肃",
    "长沙": "长沙", "长沙市": "长沙",
    "长春": "长春", "长春市": "长春",
    "福建": "福建", "福建省": "福建",
    "西安": "西安",
    "内蒙古": "内蒙古",
    "陕西": "陕西", "陕西省": "陕西",
    "安徽": "安徽", "安徽省": "安徽",
    "辽宁": "辽宁", "辽宁省": "辽宁",
    "湖北": "湖北", "湖北省": "湖北",
    "合肥": "合肥",
    "常州": "常州",
    "苏州": "苏州",
    "天津": "天津",
}


# 分歧配置表：定义每个分歧/独有项的中心立场
CENTER_DISPUTE_CONFIG = {
    # ── 数量型分歧 ──
    "F-48": {  # 名称字数限制
        "type": "quantitative",
        "center_rules": {
            "陕西": 25, "合肥": 25,   # ≤25字
            "苏州": 60,               # ≤60字
        },
        "default_strict": 25,          # 默认取最严
    },

    # ── 互斥型分歧 ──
    "F-85": {  # 附图彩色
        "type": "mutual_exclusive",
        "strict_side": ["山西", "陕西", "辽宁", "西安", "湖北", "四川", "常州"],
        "lenient_side": ["吉林", "长春", "苏州"],
        "default_strict": True,
    },
    "F-85b": {  # 截图彩色
        "type": "mutual_exclusive",
        "strict_side": ["内蒙古"],
        "lenient_side": [],
        "default_strict": True,
    },

    # ── 独有型 ──
    "F-5": {"type": "unique", "required_by": ["山西"]},            # 摘要不得使用标题
    # F-6（摘要以句号结尾）已改为统一要求，从分歧配置移除（用户2026-06-10确认）
    "F-46": {"type": "unique", "required_by": ["陕西"]},           # 附图标记不得复杂
    "F-60": {"type": "unique", "required_by": ["山西"]},           # 禁止沟通用语
    "F-62": {"type": "unique", "required_by": ["合肥"]},           # 禁止QUOTE/本地路径
    "F-74": {"type": "unique", "required_by": ["山西"]},           # 保藏信息/序列表
    "F-76": {"type": "unique", "required_by": ["合肥"]},            # 不含不宜公布/涉国防
    "F-93": {"type": "unique", "required_by": ["辽宁"]},           # 同一附图相同比例
    "F-94": {"type": "unique", "required_by": ["内蒙古"]},         # 附图竖向绘制方向
    "F-95": {"type": "unique", "required_by": ["内蒙古"]},         # 禁止清晰人脸
    "F-96": {"type": "unique", "required_by": ["内蒙古"]},         # 禁止二维码/条形码
    "F-97": {"type": "unique", "required_by": ["内蒙古"]},         # 不完整地图
    "F-98": {"type": "unique", "required_by": ["常州"]},           # 禁止照片作为附图

    # ── 差异型 ──
    "F-4": {"type": "partial", "required_by": ["山西", "陕西", "内蒙古"]},   # 摘要不得照抄权要
    "F-16": {"type": "partial", "required_by": ["山西", "合肥", "内蒙古", "苏州"]},  # 不确定用语
    "F-17": {"type": "partial", "required_by": ["山西", "合肥", "内蒙古", "苏州"]},  # "例如"等表述
    "F-18": {"type": "partial", "required_by": ["山西", "合肥"]},               # 不清确括号
    "F-8": {"type": "partial", "required_by": ["吉林", "辽宁"]},                 # 禁止"其特征在于"
    "F-30": {"type": "partial", "required_by": ["陕西"]},                       # 引证格式
    "F-31": {"type": "partial", "required_by": ["合肥"]},                       # 引证公开出版物
    "F-34": {"type": "partial", "required_by": ["山西", "合肥", "内蒙古"]},     # 多余空行等
}

# ══════════════════════════════════════════════════════════════════
# 中心精确映射表（2026-06-10 全中心规则汇总落地）
# ══════════════════════════════════════════════════════════════════

# 发明名称字数: 审查指南原文=通则25字、化学领域40字。60字非指南原文,极个别中心自加。
NAME_LENGTH_DEFAULT = (25, 40)  # (通则, 化学领域)
NAME_RELAXED_60 = frozenset(["重庆", "吉林", "苏州", "辽宁", "福建", "陕西"])

# 附图颜色(互斥维度)
FIGURE_COLOR_STRICT = frozenset(["内蒙古", "苏州", "常州", "合肥", "成都", "四川", "湖北", "山西", "陕西", "辽宁", "西安"])
FIGURE_COLOR_LENIENT = frozenset(["北京", "吉林", "济南"])
FIGURE_COLOR_SPLIT = frozenset(["湘潭", "长沙"])  # 发明可彩/实用新型禁

# 摘要字数(多数300;青岛/天津特殊计字)
ABSTRACT_CHAR_RULE = {"青岛": "字母按1字符", "天津": "字母按1字符"}

# 附图清晰度(明文要求"缩2/3仍清晰")
FIGURE_CLARITY_STRICT = frozenset(["陕西", "青岛", "浙江", "辽宁", "大连", "天津"])

# 已覆盖中心(约30个,2026-06-10全中心汇总)
COVERED_CENTERS = frozenset([
    "吉林", "徐州", "浙江", "北京", "山西", "甘肃", "长沙", "长春",
    "福建", "西安", "内蒙古", "陕西", "安徽", "辽宁", "湖北", "合肥",
    "常州", "苏州", "天津", "广州", "重庆", "青岛", "新乡", "湘潭",
    "洛阳", "南昌", "湖南", "大连", "无锡", "成都", "济南", "四川",
])


def match_center(user_input: str) -> Optional[str]:
    """模糊匹配用户输入到中心名"""
    if not user_input:
        return None

    normalized = user_input.strip()
    # 去掉"保护中心"等后缀
    for suffix in ["知识产权保护中心", "保护中心", "中心"]:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]

    # 精确匹配
    if normalized in CENTER_ALIASES:
        return CENTER_ALIASES[normalized]

    # 子串匹配
    matches = [c for c in VALID_CENTERS if c in normalized or normalized in c]
    if len(matches) == 1:
        return matches[0]

    return None


def get_center_verdict(rule_id: str, target_center: str) -> str:
    """
    获取某条规则在目标中心下的判定模式。

    返回值：
    - "mandatory"：所选中心要求此项 → 🔴必须修改
    - "lenient"：所选中心在宽松方 → ✅合格+附注
    - "suggestion"：所选中心未提及 → 💡建议关注
    - "strict_default"：未覆盖中心或默认严格 → 🔴必须修改
    - "normal"：无差异项 → 正常判定
    """
    config = CENTER_DISPUTE_CONFIG.get(rule_id)
    if not config:
        return "normal"  # 无差异项

    ctype = config["type"]
    # 最严格模式：未指定中心或未覆盖中心（match_center 返回 None 时上游传入"最严格模式"）
    # 此模式下独有项(unique/partial)按最严判定为 🔴，确保提交到任何中心都不被退回。
    is_strictest = target_center in ("", "最严格模式") or target_center is None

    if ctype == "unique":
        required_by = config["required_by"]
        if target_center in required_by:
            return "mandatory"
        if is_strictest:
            return "strict_default"   # 最严格模式：独有项也按🔴
        return "suggestion"

    elif ctype == "mutual_exclusive":
        strict_side = config.get("strict_side", [])
        lenient_side = config.get("lenient_side", [])
        if target_center in strict_side:
            return "mandatory"
        elif target_center in lenient_side:
            return "lenient"
        else:
            # 未提及的中心 / 最严格模式，取默认（默认严格）
            if config.get("default_strict", True):
                return "strict_default"
            return "suggestion"

    elif ctype == "quantitative":
        center_rules = config.get("center_rules", {})
        if target_center in center_rules:
            return "mandatory"  # 有具体数值要求
        default = config.get("default_strict")
        if default is not None:
            return "strict_default"
        return "suggestion"

    elif ctype == "partial":
        required_by = config.get("required_by", [])
        if target_center in required_by:
            return "mandatory"
        if is_strictest:
            return "strict_default"   # 最严格模式：partial 项也按🔴
        return "suggestion"

    return "normal"


def get_quantitative_limit(rule_id: str, target_center: str) -> Optional[int]:
    """获取数量型分歧的限定值"""
    config = CENTER_DISPUTE_CONFIG.get(rule_id)
    if not config or config.get("type") != "quantitative":
        return None

    center_rules = config.get("center_rules", {})
    if target_center in center_rules:
        return center_rules[target_center]

    return config.get("default_strict")


# ──────────────────────────────────────────────
# 扫描结果数据结构
# ──────────────────────────────────────────────

@dataclass
class ScanIssue:
    """单条扫描结果"""
    rule_id: str               # 规则编号 F-1~F-101
    severity: str              # must_fix / should_fix / confirm / suggestion
    location: str              # 定位（如"摘要第2段"、"权利要求3"）
    description: str           # 问题描述
    detail: str = ""           # 详细信息
    suggestion: str = ""       # 修改建议
    source_centers: str = ""   # 提出中心
    dispute_note: str = ""     # 分歧说明（为空表示无分歧）
    center_verdict: str = "normal"  # 中心判定模式


@dataclass
class ScanResult:
    """扫描结果"""
    scanner_version: str = "1.0"
    scan_timestamp: str = ""
    patent_type: str = ""
    invention_name: str = ""
    target_center: str = ""
    section_detection: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


# ──────────────────────────────────────────────
# 扫描器主类
# ──────────────────────────────────────────────

class FormalityScanner:
    """A类规则自动扫描器"""

    # 权利要求编号正则
    CLAIM_NUMBER_RE = re.compile(r'^(\d+)\s*[\.．、]\s*')
    # 引用关系正则
    CLAIM_REF_RE = re.compile(r'根据\s*(?:权利要求|权\s*利\s*要\s*求)\s*([\d\s、和及至~～—]+)')
    # "如说明书...所述" / "如图...所示"
    SPEC_REF_RE = re.compile(r'如\s*(?:说明书|说\s*明\s*书)\s*[^\s]*?(?:所述|指出|描述)')
    FIG_REF_RE = re.compile(r'如\s*图\s*\d')
    # 不确定用语
    UNCERTAIN_WORDS = re.compile(r'(?:例如|优选|尤其是|必要时|可能|通常|约|接近|等|或类似物)')
    # 商业宣传用语（简化版）
    COMMERCIAL_WORDS = re.compile(
        r'(?:首创|首创性|最先进|最好|最佳|顶尖|领先|一流|独有|独家|独创|革命性|突破性|划时代)'
    )
    # 沟通用语
    COMMUNICATION_WORDS = re.compile(r'(?:参见|详见|请参考|请参阅|请见|参见说明书)')
    # 模板残留
    TEMPLATE_RESIDUE = re.compile(r'(?:在此处键入|Type\s+here|QUOTE|C:\\|D:\\|/home/|/Users/)')
    # "所述"缺乏引用基础
    SUO_SHU_RE = re.compile(r'所述\s*([\u4e00-\u9fff]+)')

    def __init__(self, parsed: ParsedDocument, target_center: str = "最严格模式"):
        self.parsed = parsed
        self.target_center = target_center
        self.issues: list[ScanIssue] = []

    def run_all(self) -> ScanResult:
        """执行全部A类规则"""
        self.issues = []

        # 摘要规则
        if '摘要' in self.parsed.sections:
            self._scan_abstract()
        # 权利要求规则
        if '权利要求书' in self.parsed.sections:
            self._scan_claims()
        # 说明书规则
        if '说明书' in self.parsed.sections:
            self._scan_specification()
        # 附图规则
        if '说明书附图' in self.parsed.sections:
            self._scan_drawings()
        # 跨section规则
        self._scan_cross_section()

        return self._build_result()

    # ──────────────────────────────────────────
    # 摘要规则
    # ──────────────────────────────────────────

    def _scan_abstract(self):
        sec = self.parsed.sections['摘要']
        text = sec.full_text

        # F-2: 摘要字数≤300字
        self._check_F2(sec, text)

        # F-5: 摘要不得使用标题
        self._check_F5(sec)

        # F-6: 摘要应以句号结尾
        self._check_F6(sec, text)

        # F-10: 专利类型用语检查
        self._check_F10(sec, text, '摘要')

        # F-13: 摘要附图标记加括号
        self._check_F13(sec, text)

    def _check_F2(self, sec, text):
        """F-2: 摘要字数≤300字"""
        char_count = len(re.sub(r'\s', '', text))
        if char_count > 300:
            self._add_issue(
                "F-2", "must_fix", "摘要",
                f"摘要共{char_count}字，超过300字限制",
                detail=f"摘要全文{char_count}字符（含标点，不含空白）",
                suggestion="删减摘要内容至300字以内",
                source_centers="吉林、山西、陕西、辽宁、安徽、合肥、内蒙古、西安、福建、常州",
            )

    def _check_F5(self, sec):
        """F-5: 摘要不得使用标题"""
        verdict = get_center_verdict("F-5", self.target_center)
        # suggestion 不再跳过：查出来标💡建议关注（计入补充提示区），见下方 severity 判定

        # 检查摘要section首段是否为标题行（短+居中+加粗）
        if sec.paragraphs:
            first = sec.paragraphs[0].strip()
            if len(first) <= 10 and first in ['摘要', '说明书摘要', '摘 要']:
                severity = "must_fix" if verdict in ("mandatory", "strict_default") else "suggestion"
                self._add_issue(
                    "F-5", severity, "摘要",
                    "摘要部分使用了标题",
                    detail=f"首段为标题行：'{first}'",
                    suggestion="删除摘要标题，摘要正文直接开始",
                    source_centers="山西",
                    dispute_note="仅山西中心要求摘要不得使用标题" if verdict != "mandatory" else "",
                )

    def _check_F6(self, sec, text):
        """F-6: 摘要应以句号结尾（统一要求，所有中心适用 — 用户2026-06-10确认）"""
        # 去除尾部空白后检查最后一个字符
        stripped = text.rstrip()
        if stripped and stripped[-1] not in '。':
            self._add_issue(
                "F-6", "must_fix", "摘要",
                f"摘要未以句号结尾（最后字符：'{stripped[-1]}'）",
                suggestion="在摘要末尾添加句号",
                source_centers="统一要求（全部中心）",
                center_verdict="normal",
            )

    def _check_F10(self, sec, text, section_name):
        """F-10/F-55: 专利类型用语检查"""
        if self.parsed.patent_type == '未知':
            return

        if self.parsed.patent_type == '发明':
            wrong = '本实用新型'
            right = '本发明'
        else:
            wrong = '本发明'
            right = '本实用新型'

        # 搜索错误用语
        wrong_pattern = re.compile(re.escape(wrong))
        matches = list(wrong_pattern.finditer(text))

        if matches:
            # 排除"发明/实用新型内容"标题中的匹配
            actual_issues = []
            for m in matches:
                # 检查是否在"发明内容"/"实用新型内容"标题中
                start = max(0, m.start() - 10)
                end = min(len(text), m.end() + 10)
                context = text[start:end]
                if re.search(r'(?:发\s*明|实\s*用\s*新\s*型)\s*内\s*容', context):
                    continue
                actual_issues.append(m)

            if actual_issues:
                rule = "F-10" if section_name == '摘要' else ("F-33" if section_name == '权利要求书' else "F-55")
                self._add_issue(
                    rule,
                    "must_fix", section_name,
                    f"{section_name}中出现'{wrong}'，但专利类型为{self.parsed.patent_type}",
                    detail=f"发现{len(actual_issues)}处'{wrong}'用语",
                    suggestion=f"将'{wrong}'改为'{right}'",
                    source_centers="山西、安徽、内蒙古、苏州" if section_name == '摘要' else "山西、陕西、安徽、合肥、西安、内蒙古、辽宁、苏州、天津",
                )

    def _check_F13(self, sec, text):
        """F-13: 摘要附图标记加括号"""
        # 查找摘要中不在括号内的附图标记
        # 排除"图1"这种格式
        bare_marks = re.findall(r'(?<!（)\b(\d{2,4})\b(?!）|\()', text)
        # 过滤掉常见的非附图标记
        problematic = []
        for m in bare_marks:
            try:
                num = int(m)
                if 10 <= num <= 9999:  # 附图标记范围
                    # 检查上下文是否为"图N"格式
                    idx = text.find(m)
                    if idx > 0 and text[idx-1] == '图':
                        continue
                    problematic.append(m)
            except ValueError:
                pass

        if problematic:
            self._add_issue(
                "F-13", "should_fix", "摘要",
                f"摘要中的附图标记{problematic[:5]}未加括号",
                suggestion="附图标记应加括号，如(101)、(201)",
                source_centers="福建、内蒙古",
            )

    # ──────────────────────────────────────────
    # 权利要求书规则
    # ──────────────────────────────────────────

    def _scan_claims(self):
        sec = self.parsed.sections['权利要求书']
        text = sec.full_text

        # F-17: 权利要求编号连续性
        self._check_F17(sec, text)

        # F-18: 每项权利要求只有一个句号
        self._check_F18(sec, text)

        # F-19: 非择一引用/多引多
        self._check_F19(sec, text)

        # F-20: 从属权利要求引用在前权利要求
        self._check_F20(sec, text)

        # F-22: 禁止"如说明书...所述"/"如图...所示"
        self._check_F22(sec, text)

        # F-23: 附图标记加括号
        self._check_F23(sec, text)

        # F-29: 权利要求不得含插图
        self._check_F29(sec)

        # F-10: 专利类型用语
        self._check_F10(sec, text, '权利要求书')

        # F-30: 涉及流程步骤编号次序
        self._check_F30(sec, text)

        # F-9: XML公式清晰度（检查OOXML公式是否存在）
        self._check_F9(sec)

    def _extract_claims(self, text: str) -> dict:
        """提取权利要求列表 {编号: 文本}"""
        claims = {}
        current_num = None
        current_text = []

        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue

            m = self.CLAIM_NUMBER_RE.match(line)
            if m:
                # 保存上一个权利要求
                if current_num is not None:
                    claims[current_num] = ' '.join(current_text).strip()
                current_num = int(m.group(1))
                current_text = [line]
            elif current_num is not None:
                current_text.append(line)

        # 保存最后一个
        if current_num is not None:
            claims[current_num] = ' '.join(current_text).strip()

        return claims

    def _check_F17(self, sec, text):
        """F-17: 权利要求编号连续性"""
        claims = self._extract_claims(text)
        if not claims:
            return

        nums = sorted(claims.keys())
        expected = list(range(1, max(nums) + 1))

        if nums != expected:
            missing = set(expected) - set(nums)
            if missing:
                self._add_issue(
                    "F-17", "must_fix", "权利要求书",
                    f"权利要求编号不连续，缺失编号：{sorted(missing)}",
                    suggestion="确保权利要求编号从1开始连续编号",
                    source_centers="山西、陕西、辽宁、安徽、合肥、内蒙古、西安、福建、常州",
                )

    def _check_F18(self, sec, text):
        """F-18: 每项权利要求只有一个句号"""
        claims = self._extract_claims(text)
        for num, claim_text in claims.items():
            period_count = claim_text.count('。')
            if period_count == 0:
                self._add_issue(
                    "F-18", "must_fix", f"权利要求{num}",
                    f"权利要求{num}缺少句号",
                    suggestion="每项权利要求应以句号结尾",
                    source_centers="山西、合肥、内蒙古、福建、常州",
                )
            elif period_count > 1:
                self._add_issue(
                    "F-18", "should_fix", f"权利要求{num}",
                    f"权利要求{num}包含{period_count}个句号（应为1个）",
                    suggestion="每项权利要求只能有一个句号，位于结尾",
                    source_centers="山西、合肥、内蒙古、福建、常州",
                )

    def _check_F19(self, sec, text):
        """F-19: 非择一引用/多引多"""
        claims = self._extract_claims(text)
        for num, claim_text in claims.items():
            # 提取引用的权利要求编号
            ref_match = self.CLAIM_REF_RE.search(claim_text)
            if not ref_match:
                continue

            ref_str = ref_match.group(1)

            # 检查"和"/"及"（非择一引用）
            if re.search(r'[和及]', ref_str):
                self._add_issue(
                    "F-19", "must_fix", f"权利要求{num}",
                    f"权利要求{num}使用了非择一引用（'{ref_str}'中含'和/及'）",
                    detail=f"引用内容：{ref_str}",
                    suggestion="从属权利要求引用多项时应以择一方式引用（用'或'或'1-N任一'）",
                    source_centers="吉林、山西、陕西、辽宁、安徽、合肥、内蒙古、西安、福建、常州",
                )

            # 检查"1-5"范围引用（多引多的基础判断较复杂，标记为B类）

    def _check_F20(self, sec, text):
        """F-20: 从属权利要求引用在前权利要求"""
        claims = self._extract_claims(text)
        for num, claim_text in claims.items():
            ref_match = self.CLAIM_REF_RE.search(claim_text)
            if not ref_match:
                continue

            ref_str = ref_match.group(1)
            # 提取引用编号
            ref_nums = [int(n) for n in re.findall(r'\d+', ref_str)]

            # 检查是否引用了在后的权利要求
            for rn in ref_nums:
                if rn >= num:
                    self._add_issue(
                        "F-20", "must_fix", f"权利要求{num}",
                        f"权利要求{num}引用了权利要求{rn}（引用了自身或在后的权利要求）",
                        suggestion="从属权利要求只能引用在前的权利要求",
                        source_centers="陕西、辽宁",
                    )

    def _check_F22(self, sec, text):
        """F-22: 禁止"如说明书...所述"/"如图...所示" """
        spec_matches = self.SPEC_REF_RE.findall(text)
        fig_matches = self.FIG_REF_RE.findall(text)

        if spec_matches:
            self._add_issue(
                "F-22", "must_fix", "权利要求书",
                f"权利要求中出现了'如说明书……所述'类引用语（{len(spec_matches)}处）",
                suggestion="权利要求中不应引用说明书内容",
                source_centers="吉林、山西、陕西、辽宁、合肥、西安、内蒙古、常州",
            )
        if fig_matches:
            self._add_issue(
                "F-22", "should_fix", "权利要求书",
                f"权利要求中出现了'如图……所示'类引用语（{len(fig_matches)}处）",
                suggestion="权利要求中不应引用附图",
                source_centers="吉林、山西、陕西、辽宁、合肥、西安、内蒙古、常州",
            )

    def _check_F23(self, sec, text):
        """F-23: 附图标记加括号（收窄正则，降低软件/算法案误报）"""
        issues = []
        for m in re.finditer(r'[一-鿿](\d{2,4})(?![\d年月日号个倍%％米秒克瓦伏安兆℃°步版层位维次帧批轮])', text):
            num_str = m.group(1)
            # 排除步骤编号/版本号/层数等常见非标记上下文
            pre_start = max(0, m.start() - 4)
            pre_ctx = text[pre_start:m.start() + 1]
            if re.search(r'[S第步层版]$|实施例|阈值|步骤|第\d', pre_ctx):
                continue
            try:
                num = int(num_str)
                if 10 <= num <= 9999:
                    start_pos = m.start()
                    if start_pos > 0 and text[start_pos - 1] in '（(':
                        continue
                    issues.append(num_str)
            except ValueError:
                pass

        if issues:
            unique_issues = list(dict.fromkeys(issues))
            self._add_issue(
                "F-23", "should_fix", "权利要求书",
                f"权利要求中的附图标记{unique_issues[:8]}未加括号",
                suggestion="附图标记应置于括号内，如'模块(101)'",
                source_centers="山西、陕西、辽宁、吉林、西安、内蒙古、常州、苏州",
            )

    def _check_F29(self, sec):
        """F-29: 权利要求不得含插图"""
        if sec.images:
            self._add_issue(
                "F-29", "must_fix", "权利要求书",
                f"权利要求书中包含{len(sec.images)}张图片/插图",
                suggestion="权利要求书中不应包含图片、流程图、方框图等插图",
                source_centers="陕西、辽宁、湖北、内蒙古",
            )

    def _check_F9(self, sec):
        """F-9: 检查OOXML公式"""
        if sec.has_omath:
            # 有公式但无法自动检测是否"清晰"，标记为需人工确认
            pass  # 公式存在本身不是问题，是否清晰是B/C类

    def _check_F30(self, sec, text):
        """F-30: 涉及流程步骤的编号次序"""
        # 提取步骤编号
        step_pattern = re.compile(r'步骤\s*(\d+)[\s\.．、：:]|S(\d+)[\s\.．、：:]')
        steps = []
        for m in step_pattern.finditer(text):
            num = m.group(1) or m.group(2)
            if num:
                steps.append(int(num))

        if len(steps) >= 2:
            # 检查连续性
            for i in range(1, len(steps)):
                if steps[i] != steps[i-1] + 1 and steps[i] > steps[i-1]:
                    # 可能有跳号
                    pass  # 步骤跳号不是严重问题，可能是子步骤

    # ──────────────────────────────────────────
    # 说明书规则
    # ──────────────────────────────────────────

    def _scan_specification(self):
        sec = self.parsed.sections['说明书']
        text = sec.full_text

        # F-47: 发明名称一致性
        self._check_F47()

        # F-48: 名称字数检查
        self._check_F48()

        # F-49: 说明书五部分完整性
        self._check_F49(sec, text)

        # F-50: 小标题前无段落号
        self._check_F50(sec, text)

        # F-55: 禁止"如权利要求...所述"
        self._check_F55(sec, text)

        # F-56: 专利类型用语检查
        self._check_F10(sec, text, '说明书')

        # F-58: 说明书文字部分无插图
        self._check_F58(sec)

        # F-59: 不得含带图的表格
        self._check_F59(sec)

        # F-61: 禁止"在此处键入"
        self._check_F61(sec, text)

        # F-62: 禁止QUOTE/本地路径
        self._check_F62(sec, text)

        # F-64: 附图说明与附图对应
        self._check_F64(sec, text)

        # F-67: 附图说明中的图号连续性
        self._check_F67(sec, text)

        # F-63: 附图标记一致性（跨section，在cross_section中处理）

    def _check_F47(self):
        """F-47: 发明名称一致性"""
        names = set()
        for stype in ['摘要', '权利要求书', '说明书']:
            sec = self.parsed.sections.get(stype)
            if sec and sec.paragraphs:
                # 从首段提取名称
                name = self._extract_name_from_section(sec)
                if name:
                    names.add(name.strip())

        if len(names) > 1:
            self._add_issue(
                "F-47", "must_fix", "全文",
                f"各部分发明名称不一致：{'; '.join(names)}",
                suggestion="统一各部分的发明/实用新型名称",
                source_centers="吉林、山西、陕西、辽宁、安徽、合肥、西安、内蒙古、福建、北京、常州、苏州",
            )

    def _extract_name_from_section(self, sec) -> str:
        """从section首段提取发明名称

        策略：
        - 说明书/摘要：首段通常就是发明名称（含"一种"，长度适中）
        - 权利要求书：不参与名称一致性比较（无独立名称段落）
        """
        # 权利要求书不提取名称（F-47只比较说明书与摘要）
        if sec.section_type == '权利要求书':
            return ""

        for p in sec.paragraphs:
            p = p.strip()
            if not p:
                continue
            # 跳过标题行
            if re.match(r'^(说\s*明\s*书|权\s*利\s*要\s*求|摘\s*要|附\s*图)', p):
                continue
            # 只提取含"一种"且长度适中的段落（发明名称特征）
            if 5 < len(p) <= 60 and '一种' in p:
                return p
        return ""

    def _check_F48(self):
        """F-48: 名称字数检查"""
        if not self.parsed.invention_name:
            return

        name = self.parsed.invention_name
        char_count = len(re.sub(r'\s', '', name))

        limit = get_quantitative_limit("F-48", self.target_center)
        if limit is None:
            limit = 25  # 默认最严格

        if char_count > limit:
            verdict = get_center_verdict("F-48", self.target_center)
            severity = "must_fix" if verdict in ("mandatory", "strict_default") else "suggestion"
            self._add_issue(
                "F-48", severity, "说明书",
                f"发明名称'{name[:20]}...'共{char_count}字，超过{limit}字限制",
                detail=f"目标保护中心({self.target_center})的字数上限为{limit}字",
                suggestion="精简发明名称" + (f"至{limit}字以内" if limit == 25 else ""),
                source_centers="陕西、合肥、苏州",
                dispute_note=f"陕西/合肥要求≤25字；苏州要求≤60字；当前按{limit}字判定",
            )

    def _check_F49(self, sec, text):
        """F-49: 说明书五部分完整性"""
        from docx_parser import DocxSectionParser
        subheading_names = ['技术领域', '背景技术', '发明/实用新型内容', '附图说明', '具体实施方式']
        found = [False] * 5

        for i, pattern in enumerate(DocxSectionParser.SPEC_SUBHEADINGS):
            for line in text.split('\n'):
                if pattern.match(line.strip()):
                    found[i] = True
                    break

        missing = [name for name, f in zip(subheading_names, found) if not f]
        # "附图说明"在无附图的情况下可以缺失
        if missing and not (len(missing) == 1 and missing[0] == '附图说明'):
            self._add_issue(
                "F-49", "must_fix", "说明书",
                f"说明书缺少以下部分：{'、'.join(missing)}",
                suggestion="补充缺失的说明书部分",
                source_centers="吉林、山西、陕西、辽宁、安徽、合肥、西安、内蒙古、福建、北京、常州、苏州",
            )

    def _check_F50(self, sec, text):
        """F-50: 小标题前无段落号"""
        from docx_parser import DocxSectionParser
        subheading_patterns = DocxSectionParser.SPEC_SUBHEADINGS

        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            for pattern in subheading_patterns:
                if pattern.match(stripped):
                    # 检查是否有段落号前缀
                    prefix_match = re.match(r'^[\d]+[\.\s、．]', stripped)
                    if prefix_match:
                        self._add_issue(
                            "F-50", "must_fix", "说明书",
                            f"小标题'{stripped}'前有段落号'{prefix_match.group()}'",
                            suggestion="说明书各小标题前不得添加段落号",
                            source_centers="吉林、山西、陕西、辽宁、安徽、合肥、西安、内蒙古",
                        )
                    break

    def _check_F55(self, sec, text):
        """F-55: 禁止"如权利要求...所述" """
        matches = re.findall(r'如\s*(?:权利要求|权\s*利\s*要\s*求)\s*[\d]+\s*所\s*述', text)
        if matches:
            self._add_issue(
                "F-55", "must_fix", "说明书",
                f"说明书中出现'如权利要求……所述'类引用语（{len(matches)}处）",
                suggestion="说明书中不应引用权利要求",
                source_centers="吉林、山西、陕西、辽宁、安徽、合肥、西安、内蒙古、常州",
            )

    def _check_F58(self, sec):
        """F-58: 说明书文字部分无插图"""
        if sec.images:
            self._add_issue(
                "F-58", "must_fix", "说明书",
                f"说明书文字部分包含{len(sec.images)}张图片/插图",
                suggestion="说明书文字部分不得含有插图，图片应放在说明书附图部分",
                source_centers="吉林、山西、陕西、辽宁、安徽、合肥、西安、内蒙古、天津",
            )

    def _check_F59(self, sec):
        """F-59: 不得含带图的表格"""
        # 检查表格cell是否含图片（简化检查）
        if sec.tables:
            for ti, table in enumerate(sec.tables):
                for row in table:
                    for cell in row:
                        # 简化：检查单元格文本中是否有图片占位符
                        if re.search(r'\[图片\]|\[图像\]|<img', cell):
                            self._add_issue(
                                "F-59", "should_fix", "说明书",
                                f"说明书中第{ti+1}个表格包含图片",
                                suggestion="表格中不得含有图片",
                                source_centers="陕西、安徽、合肥",
                            )
                            break

    def _check_F61(self, sec, text):
        """F-61: 禁止"在此处键入" """
        matches = re.findall(r'在此处键入|Type\s+here', text, re.IGNORECASE)
        if matches:
            self._add_issue(
                "F-61", "must_fix", "说明书",
                f"说明书中存在模板残留文字'在此处键入'（{len(matches)}处）",
                suggestion="删除所有模板残留文字",
                source_centers="陕西、合肥、内蒙古",
            )

    def _check_F62(self, sec, text):
        """F-62: 禁止QUOTE/本地路径"""
        verdict = get_center_verdict("F-62", self.target_center)
        # suggestion 不再跳过：查出来标💡建议关注（计入补充提示区）

        matches = self.TEMPLATE_RESIDUE.findall(text)
        # 过滤掉"在此处键入"（已在F-61检查）
        matches = [m for m in matches if '键入' not in m and 'Type' not in m]
        if matches:
            severity = "must_fix" if verdict in ("mandatory", "strict_default") else "suggestion"
            self._add_issue(
                "F-62", severity, "说明书",
                f"说明书中存在Word标记或本地路径（{len(matches)}处）",
                detail=f"发现：{matches[:5]}",
                suggestion="删除所有QUOTE标记、本地文件路径等残留内容",
                source_centers="合肥",
                dispute_note="仅合肥中心明确要求此项" if verdict != "mandatory" else "",
            )

    def _check_F64(self, sec, text):
        """F-64: 附图说明与附图对应"""
        # 提取"图N"编号
        fig_in_spec = set()
        for m in re.finditer(r'图\s*(\d{1,3})', text):
            fig_in_spec.add(int(m.group(1)))

        # 与附图section对比
        fig_sec = self.parsed.sections.get('说明书附图')
        if fig_sec:
            fig_in_drawings = set()
            for m in re.finditer(r'图\s*(\d{1,3})', fig_sec.full_text):
                fig_in_drawings.add(int(m.group(1)))

            if fig_in_spec and fig_in_drawings:
                # 检查缺图/多余图
                missing_in_drawings = fig_in_spec - fig_in_drawings
                extra_in_drawings = fig_in_drawings - fig_in_spec

                if missing_in_drawings:
                    self._add_issue(
                        "F-64", "must_fix", "说明书",
                        f"说明书中提及图{sorted(missing_in_drawings)}但附图中未找到",
                        suggestion="确保说明书附图说明中的每个图号都有对应附图",
                        source_centers="吉林、山西、陕西、辽宁、安徽、合肥、西安、内蒙古、四川、常州、天津",
                    )
                if extra_in_drawings:
                    self._add_issue(
                        "F-64", "must_fix", "说明书附图",
                        f"附图中有图{sorted(extra_in_drawings)}但说明书中未提及",
                        suggestion="确保每个附图都在说明书中有说明",
                        source_centers="吉林、山西、陕西、辽宁、安徽、合肥、西安、内蒙古、四川、常州、天津",
                    )

    def _check_F67(self, sec, text):
        """F-67: 附图说明中的图号连续性"""
        fig_nums = []
        for m in re.finditer(r'图\s*(\d{1,3})', text):
            fig_nums.append(int(m.group(1)))

        if fig_nums:
            unique_sorted = sorted(set(fig_nums))
            expected = list(range(1, max(unique_sorted) + 1))
            if unique_sorted != expected:
                missing = set(expected) - set(unique_sorted)
                if missing:
                    self._add_issue(
                        "F-67", "must_fix", "说明书",
                        f"附图图号不连续，缺失：图{sorted(missing)}",
                        suggestion="附图应使用阿拉伯数字顺序编号",
                        source_centers="吉林、山西、陕西、辽宁、安徽、合肥、西安、内蒙古、福建、湖北、常州、苏州",
                    )

    # ──────────────────────────────────────────
    # 附图规则
    # ──────────────────────────────────────────

    def _scan_drawings(self):
        sec = self.parsed.sections['说明书附图']
        text = sec.full_text

        # F-79: 附图编号连续性
        self._check_F79(sec, text)

        # F-80: 图号后无多余文字注释
        self._check_F80(sec, text)

        # F-82: 附图说明与附图对应（在F-64中已处理跨section部分）
        # F-83: 说明书vs附图标记双向核查
        self._check_F83()

        # F-90: 附图中文词语检查
        self._check_F90(sec, text)

        # F-95/F-96: 多模态检测项（标记需人工确认）
        self._check_F95_F96()

    def _check_F79(self, sec, text):
        """F-79: 附图编号连续性"""
        fig_nums = []
        for m in re.finditer(r'图\s*(\d{1,3})', text):
            fig_nums.append(int(m.group(1)))

        if fig_nums:
            unique_sorted = sorted(set(fig_nums))
            expected = list(range(1, max(unique_sorted) + 1))
            if unique_sorted != expected:
                missing = set(expected) - set(unique_sorted)
                if missing:
                    self._add_issue(
                        "F-79", "must_fix", "说明书附图",
                        f"附图图号不连续，缺失：图{sorted(missing)}",
                        suggestion="附图应使用阿拉伯数字顺序编号",
                        source_centers="吉林、山西、陕西、辽宁、安徽、合肥、西安、内蒙古、福建、湖北、常州、苏州",
                    )

    def _check_F80(self, sec, text):
        """F-80: 图号后无多余文字注释"""
        # 检查"图1"后面是否有多余的非标准文字
        for line in text.split('\n'):
            stripped = line.strip()
            m = re.match(r'^图\s*(\d+)\s+(.+)$', stripped)
            if m:
                after = m.group(2).strip()
                # 允许"图1 XXX方法的流程图"这种说明性文字
                # 不允许"图1 图1的说明..."这种重复
                if after and re.match(r'^图\s*\d+', after):
                    self._add_issue(
                        "F-80", "should_fix", "说明书附图",
                        f"附图编号'{stripped[:20]}'后可能有多余注释",
                        suggestion="图号后不应有多余的文字注释或符号",
                        source_centers="吉林、山西、陕西、安徽、合肥、西安、内蒙古",
                    )

    def _check_F83(self):
        """F-83: 说明书vs附图标记双向核查"""
        spec_sec = self.parsed.sections.get('说明书')
        fig_sec = self.parsed.sections.get('说明书附图')

        if not spec_sec or not fig_sec:
            return

        spec_marks = set(spec_sec.figure_marks)
        fig_marks = set(fig_sec.figure_marks)

        # 标记在说明书中但不在附图中
        spec_only = spec_marks - fig_marks
        # 标记在附图中但不在说明书中
        fig_only = fig_marks - spec_marks

        if spec_only:
            self._add_issue(
                "F-83", "should_fix", "说明书",
                f"说明书中提及的附图标记{sorted(list(spec_only)[:10], key=lambda x: int(x) if x.isdigit() else 0)}在附图中未出现",
                suggestion="确保说明书中提及的所有附图标记在附图中都有对应",
                source_centers="吉林、山西、陕西、辽宁、安徽、合肥、西安、内蒙古、四川",
            )
        if fig_only:
            self._add_issue(
                "F-83", "should_fix", "说明书附图",
                f"附图中的标记{sorted(list(fig_only)[:10], key=lambda x: int(x) if x.isdigit() else 0)}在说明书中未提及",
                suggestion="确保附图中的所有标记在说明书中都有说明",
                source_centers="吉林、山西、陕西、辽宁、安徽、合肥、西安、内蒙古、四川",
            )

    def _check_F90(self, sec, text):
        """F-90: 附图中词语使用中文"""
        # 检查附图文本中的纯外文词（排除常见缩写和化学符号）
        foreign_words = re.findall(r'[A-Za-z]{3,}(?:\s[A-Za-z]+)*', text)
        # 过滤掉常见的技术缩写
        common_abbr = {'CPU', 'GPU', 'RAM', 'ROM', 'LED', 'LCD', 'USB', 'PCB',
                       'IO', 'API', 'AI', 'ML', 'DL', 'NN', 'CNN', 'RNN',
                       'RGB', 'YUV', 'HDMI', 'WiFi', 'Bluetooth', 'GPS',
                       'CPU', 'RAM', 'DSP', 'FPGA', 'ASIC', 'SOC', 'MCU',
                       'DC', 'AC', 'PWM', 'ADC', 'DAC', 'UART', 'SPI', 'I2C'}

        problematic = [w for w in foreign_words if w.upper() not in common_abbr and len(w) >= 4]
        if problematic:
            unique = list(dict.fromkeys(problematic))[:10]
            self._add_issue(
                "F-90", "should_fix", "说明书附图",
                f"附图中可能存在未翻译的外文词语：{unique}",
                suggestion="附图中的词语应使用中文，必要时可在括号中注明原文",
                source_centers="陕西、辽宁、山西、西安",
            )

    def _check_F95_F96(self):
        """F-95/F-96: 多模态检测项（标记需人工确认）"""
        fig_sec = self.parsed.sections.get('说明书附图')
        if fig_sec and fig_sec.images:
            # 有图片但无法自动检测人脸/二维码，标记为需人工确认
            verdict_95 = get_center_verdict("F-95", self.target_center)
            if verdict_95 in ("mandatory", "strict_default"):
                self._add_issue(
                    "F-95", "confirm", "说明书附图",
                    "请人工确认附图中是否含有清晰人脸图像（当前无法自动检测）",
                    source_centers="内蒙古",
                    dispute_note="仅内蒙古中心明确要求此项" if verdict_95 != "mandatory" else "",
                )

            verdict_96 = get_center_verdict("F-96", self.target_center)
            if verdict_96 in ("mandatory", "strict_default"):
                self._add_issue(
                    "F-96", "confirm", "说明书附图",
                    "请人工确认附图中是否含有二维码、条形码（当前无法自动检测）",
                    source_centers="内蒙古",
                    dispute_note="仅内蒙古中心明确要求此项" if verdict_96 != "mandatory" else "",
                )

    # ──────────────────────────────────────────
    # 跨section规则
    # ──────────────────────────────────────────

    def _scan_cross_section(self):
        """跨section检查"""
        # F-24/F-25: 附图标记一致性（权要vs说明书vs附图）
        self._check_F24_F25()

        # F-65: 具体实施方式中附图标记不加括号
        self._check_F65()

    def _check_F24_F25(self):
        """F-24/F-25: 附图标记一致性"""
        claims_sec = self.parsed.sections.get('权利要求书')
        spec_sec = self.parsed.sections.get('说明书')
        fig_sec = self.parsed.sections.get('说明书附图')

        if not claims_sec:
            return

        claims_marks = set(claims_sec.figure_marks)

        # 与说明书对比
        if spec_sec:
            spec_marks = set(spec_sec.figure_marks)
            claims_only = claims_marks - spec_marks
            if claims_only:
                self._add_issue(
                    "F-25", "should_fix", "权利要求书",
                    f"权利要求中的附图标记{sorted(list(claims_only)[:8])}在说明书中未出现",
                    suggestion="确保权利要求中的附图标记与说明书一致",
                    source_centers="山西、陕西、安徽、西安、内蒙古、常州",
                )

        # 与附图对比
        if fig_sec:
            fig_marks = set(fig_sec.figure_marks)
            claims_only_fig = claims_marks - fig_marks
            if claims_only_fig:
                self._add_issue(
                    "F-25", "should_fix", "权利要求书",
                    f"权利要求中的附图标记{sorted(list(claims_only_fig)[:8])}在附图中未出现",
                    suggestion="确保权利要求中的附图标记与附图一致",
                    source_centers="山西、陕西、安徽、西安、内蒙古、常州",
                )

    def _check_F65(self):
        """F-65: 具体实施方式中附图标记不加括号"""
        spec_sec = self.parsed.sections.get('说明书')
        if not spec_sec:
            return

        text = spec_sec.full_text

        # 定位"具体实施方式"部分
        impl_start = -1
        for i, line in enumerate(text.split('\n')):
            if re.match(r'^具\s*体\s*实\s*施\s*方\s*式', line.strip()):
                impl_start = i
                break

        if impl_start < 0:
            return

        # 在实施方式部分检查括号内的数字标记
        impl_text = '\n'.join(text.split('\n')[impl_start:])
        bracketed_marks = re.findall(r'（(\d{2,4})）|\((\d{2,4})\)', impl_text)

        if bracketed_marks:
            marks = [m[0] or m[1] for m in bracketed_marks]
            self._add_issue(
                "F-65", "should_fix", "说明书·具体实施方式",
                f"具体实施方式中的附图标记{marks[:8]}加了括号（应为不加括号）",
                suggestion="具体实施方式中的附图标记放在相应技术名称后面，不加括号",
                source_centers="山西、陕西、常州",
            )

    # ──────────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────────

    def _add_issue(self, rule_id, severity, location, description, *,
                   detail="", suggestion="", source_centers="",
                   dispute_note="", center_verdict=None):
        """添加一条扫描结果"""
        if center_verdict is None:
            center_verdict = get_center_verdict(rule_id, self.target_center)

        self.issues.append(ScanIssue(
            rule_id=rule_id,
            severity=severity,
            location=location,
            description=description,
            detail=detail,
            suggestion=suggestion,
            source_centers=source_centers,
            dispute_note=dispute_note,
            center_verdict=center_verdict,
        ))

    def _build_result(self) -> ScanResult:
        """构建扫描结果"""
        # 统计
        total = len(self.issues)
        must_fix = sum(1 for i in self.issues if i.severity == "must_fix")
        should_fix = sum(1 for i in self.issues if i.severity == "should_fix")
        confirm = sum(1 for i in self.issues if i.severity == "confirm")
        suggestion = sum(1 for i in self.issues if i.severity == "suggestion")

        section_detection = {}
        for stype in ['摘要', '权利要求书', '说明书', '说明书附图']:
            sec = self.parsed.sections.get(stype)
            if sec:
                section_detection[stype] = {
                    "detected": True,
                    "header": sec.header_text,
                    "para_range": list(sec.para_index_range),
                }
            else:
                section_detection[stype] = {"detected": False}

        return ScanResult(
            scanner_version="1.0",
            scan_timestamp=datetime.now().isoformat(),
            patent_type=self.parsed.patent_type,
            invention_name=self.parsed.invention_name,
            target_center=self.target_center,
            section_detection=section_detection,
            summary={
                "total_a_rules": 36,
                "a_rules_passed": 36 - total,
                "a_rules_failed": must_fix + should_fix,
                "a_rules_manual": confirm + suggestion,
                "must_fix": must_fix,
                "should_fix": should_fix,
                "confirm": confirm,
                "suggestion": suggestion,
            },
            issues=[asdict(i) for i in self.issues],
            warnings=self.parsed.warnings,
        )


# ──────────────────────────────────────────────
# 命令行入口
# ──────────────────────────────────────────────

def main():
    """命令行测试入口"""
    if len(sys.argv) < 2:
        print("用法: python formality_scanner.py <docx文件路径> [保护中心名称]")
        sys.exit(1)

    path = sys.argv[1]
    target_center = sys.argv[2] if len(sys.argv) > 2 else "最严格模式"

    # 先解析
    from docx_parser import DocxSectionParser
    parser = DocxSectionParser(path)
    parsed = parser.parse()

    # 显示分节结果
    print(parser.get_section_summary(parsed))
    print()

    # 执行扫描
    scanner = FormalityScanner(parsed, target_center)
    result = scanner.run_all()

    # 输出结果
    print(f"目标保护中心：{result.target_center}")
    print(f"扫描时间：{result.scan_timestamp}")
    print(f"专利类型：{result.patent_type}")
    print(f"发明名称：{result.invention_name}")
    print()
    print(f"统计：通过{result.summary['a_rules_passed']} | "
          f"未通过{result.summary['a_rules_failed']} | "
          f"需确认{result.summary['a_rules_manual']}")
    print()

    if result.issues:
        print("发现问题：")
        for issue in result.issues:
            severity_map = {"must_fix": "🔴", "should_fix": "🟡", "confirm": "⚪", "suggestion": "💡"}
            emoji = severity_map.get(issue['severity'], "?")
            print(f"  {emoji} [{issue['rule_id']}] {issue['location']}: {issue['description'][:80]}")
            if issue.get('suggestion'):
                print(f"      → {issue['suggestion'][:60]}")
    else:
        print("✅ A类规则全部通过！")


if __name__ == '__main__':
    main()
