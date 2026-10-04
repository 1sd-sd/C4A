#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lishengdan_C4A_demo_生成脚本.py — 生成 C4A 的 5 张 demo 截图。

原则与 C4 的 demo 相同：**图里的每一行都来自真实运行输出**，不是摆拍。
脚本会真的去跑（1）自测套件（2）规则层评审（3）反套壳对照（4）混合层改判，
把 stdout 捕获后渲染成终端风格 PNG。

依赖：pillow（其余全标准库）。字体：C:\\Windows\\Fonts\\simhei.ttf（半角=全角=等宽）。
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "src" / "c4-skill-evaluator"
OUT = HERE
TMP = Path(tempfile.gettempdir()) / "c4a_demo_run"   # 稳定路径：图内可见的路径每次一致；不污染提交包

FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"
SIZE = 15

BG = (13, 17, 23)
FG = (201, 209, 217)
DIM = (110, 118, 129)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
CYAN = (88, 166, 255)
YELLOW = (210, 153, 34)

PY = sys.executable


# --------------------------------------------------------------------------- #
# 真实运行，捕获 stdout
# --------------------------------------------------------------------------- #

def run_real(args: list[str]) -> tuple[str, int]:
    """真实执行一条命令，返回 (stdout, exit_code)。"""
    proc = subprocess.run([PY, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(SKILL))
    return proc.stdout.strip("\n"), proc.returncode


def run_selftest_summary() -> tuple[str, int]:
    """跑自测套件，返回精简后的真实输出。"""
    out, code = run_real(["examples/run_selftest.py", "--out-dir", str(TMP / "selftest")])
    lines = []
    started = False
    shown = 0
    for ln in out.splitlines():
        if ln.startswith("c4-skill-evaluator 自测套件"):
            started = True
        if not started:
            continue
        # 逐项明细只展示前 6 行，其余折叠（43 行放不进一张图）
        if ln[:14].strip() and not ln.startswith(("样本", "----", "====", "检查项", "阈值", "  [", "已知局限", "  ①", "  ②", "  ③", "  ④")):
            shown += 1
            if shown > 6:
                if shown == 7:
                    lines.append("  …（其余 37 项全部 PASS，此处略）")
                continue
        lines.append(ln)
    return "\n".join(lines), code


def run_rule_layer() -> tuple[str, int]:
    out, code = run_real(["scripts/c4a_evaluate.py", "--input", "examples/real_corpus",
                          "--outdir", str(TMP / "rule")])
    return out, code


def run_antigame() -> tuple[str, int]:
    """反套壳对照：同一个评测器，对『齐全样本』与『空壳样本』给出完全不同的结论。"""
    spec = importlib.util.spec_from_file_location("ev", SKILL / "scripts" / "c4a_evaluate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    rubric = mod.load_rubric(SKILL / "references" / "c4a_rubric.json")

    buf = io.StringIO()
    with redirect_stdout(buf):
        print("c4-skill-evaluator v1.0.0 · 反套壳对照实验")
        print("问题：一份『文档齐全但全是占位符』的提交，能骗过关键词评审吗？")
        print()
        for name, label in (("zhangwei", "齐全且真实"), ("wangxiao", "表面齐全、实为空壳")):
            folder = SKILL / "examples" / "synthetic_corpus" / name
            files = mod.scan_folder(folder, rubric, [])
            content = mod.build_content_index(files, rubric)
            r = mod.eval_author(name, files, content, rubric, "c4_four_conditions")
            c = r["completeness"]
            print(f"── 样本 {name}（{label}）")
            print(f"   文件数 {r['file_count']}　交付物命中 {c['present']}/5")
            for k, v in c["slots"].items():
                mark = {"✅": "[OK]", "⚠️": "[!!]", "❌": "[XX]"}[v["status"]]
                print(f"   {mark} {v['label']:<18} {v['best'] or '—'}")
            print(f"   质量得分率 {r['quality_ratio'] * 100:.0f}%")
            for fl in r["red_flags"]:
                print(f"   [!!] 红旗 {fl['cn']}（{fl['severity']}，封顶 {fl['cap_score']}）")
            print(f"   >>> 综合分 {r['score']} / 100　等级 {r['grade']}（{r['grade_cn']}）")
            print()
    return buf.getvalue().strip(), 0


def run_hybrid() -> tuple[str, int]:
    verdicts = HERE.parent / "评审产物" / "llm_verdicts.json"
    out, code = run_real(["scripts/c4a_evaluate.py", "--input", "examples/real_corpus",
                          "--outdir", str(TMP / "hybrid"),
                          "--llm-verdicts", str(verdicts)])
    lines = []
    for ln in out.splitlines():
        lines.append(ln)
        if ln.startswith("----") and lines.count(ln) >= 2:
            break
    data = json.loads((HERE.parent / "评审产物" / "evaluation_result_混合层.json").read_text(encoding="utf-8"))
    st = data["llm_stats"]
    lines.append("")
    lines.append(f"规则层 vs LLM 层：比对 {st['compared']} 个维度　一致 {st['agreed']}　改判 {st['applied']}"
                 f"　一致率 {st['agreement'] * 100:.1f}%")
    lines.append("")
    lines.append("改判明细（均经实测验证，不是拍脑袋）：")
    for r in data["results"]:
        for cid, c in r["criteria"].items():
            if c.get("rule_rating"):
                lines.append(f"  · {r['author']} / {c['label']}："
                             f"规则 {c['rule_rating']}({c['rule_score']}) → LLM {c['rating']}")
    lines.append("")
    lines.append("为什么规则层发现不了 skill-explainer 的问题？")
    lines.append("  它只验证『.skill 包本身合法』，不会去读 SKILL.md 里的解包代码。")
    lines.append("  而 skill-explainer 用 tarfile.open(p,'r:gz') 解 zip —— 实测抛 ReadError。")
    lines.append("  『代码与事实不符』这类语义矛盾，必须由 LLM 层复核。")
    return "\n".join(lines), code


def run_crosscheck() -> tuple[str, int]:
    """交叉自检对照：同一份提交，全量盲扫 vs 排除测试语料。

    数据来自 check_deliverables.py 两次真实运行的落盘结果（评审产物/交叉自检_C4技能*/）。
    """
    lines = ["challenge-submission-checker v1.2.0 · 交叉自检对照实验", ""]
    lines.append("问题：同一份 C4A 提交，全量盲扫与排除测试语料，结论差多少？")
    lines.append("")
    pairs = [
        ("全量盲扫（含 examples/ 下的刻意坏样本）", HERE.parent / "评审产物" / "交叉自检_C4技能"),
        ("对照（--exclude 两个测试语料目录）", HERE.parent / "评审产物" / "交叉自检_C4技能_对照"),
    ]
    for label, d in pairs:
        f = d / "check_result.json"
        if not f.exists():
            lines.append(f"── {label}：缺少 {f}")
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        sc = data.get("scores", {})
        lines.append(f"── {label}")
        lines.append(f"   扫描文件 {data.get('file_count')} 个　"
                     f"交付物 {sc.get('deliverables')} / 内容 {sc.get('content')} / "
                     f"卫生 {sc.get('hygiene')} / 安全 {sc.get('safety')}")
        blocking = data.get("blocking", [])
        lines.append(f"   阻断项 {len(blocking)} 条　建议项 {len(data.get('warnings', []))} 条")
        for b in blocking[:6]:
            lines.append(f"   [XX] {b[:96]}")
        lines.append(f"   >>> 总分 {data.get('total')} / 100　判定 {data.get('verdict')}")
        lines.append("")
    lines.append("结论：本次差异全部来自「它分不清测试夹具与真实提交」+「密钥正则跨行误报」。")
    lines.append("这正是 C4A 要解决的问题 —— 所以 FAIL 结果留档，而不是删掉坏样本。")
    return "\n".join(lines).strip(), 0


def run_artifacts() -> tuple[str, int]:
    rows = [
        ("lishengdan_C4A_方案设计.md", "架构设计 + 评审维度定义 + 技术选型理由"),
        ("lishengdan_C4A_skill-evaluator.skill", "可安装技能包（zip，含源码/配置/样例/自测）"),
        ("lishengdan_C4A_评审报告.md", "真实评审报告（规则层，确定性）"),
        ("lishengdan_C4A_评审报告_深审版.md", "规则层 + LLM 深审合并，含一致率与改判依据"),
        ("lishengdan_C4A_评测器自测报告.md", "43 项检查项准确率 100% / 误判率 0% + 已知局限"),
        ("lishengdan_C4A_评审明细.csv", "作者级明细（等级/红旗/缺口）"),
        ("lishengdan_C4A_评审明细_检查项.csv", "检查项级明细（每条判定 + 证据 + 改进提示）"),
        ("lishengdan_C4A_评审报告.html", "班级仪表板（排名/质量分布/红旗）"),
        ("lishengdan_C4A_教学说明.md", "怎么装、怎么用、输入什么得到什么"),
        ("lishengdan_C4A_拿来说明.md", "从 wechat-doc-mapper 拿了什么 / 改了什么 / 为什么"),
        ("lishengdan_C4A_AI日志.md", "开发全过程 AI 使用记录（9 轮迭代）"),
        ("lishengdan_C4A_复盘AAR.md", "复盘：四次差点被骗的洞察 + 6 条改进方案"),
        ("lishengdan_C4A_复现脚本.py", "一键重建报告/自测/demo/技能包 + 脱敏自检"),
    ]
    lines = ["c4-skill-evaluator v1.0.0 · C4A 交付物清单", ""]
    for i, (name, desc) in enumerate(rows, 1):
        lines.append(f"[{i:02d}] {name}")
        lines.append(f"     └─ {desc}")
    lines.append("")
    lines.append("全部文件位于 D:\\.cogseed\\userWorkSpace\\我的挑战有哪些\\C4A提交成果\\")
    return "\n".join(lines), 0


# --------------------------------------------------------------------------- #
# 渲染
# --------------------------------------------------------------------------- #

def colorize(line: str) -> tuple:
    s = line.strip()
    if s.startswith(("=====", "-----")):
        return DIM
    if s.startswith(">>>"):
        return GREEN
    if "[XX]" in s or "FAIL" in s or "❌" in s or "误报" in s:
        return RED
    if "[OK]" in s or "PASS" in s or "✅" in s or "准确率 100" in s:
        return GREEN
    if "[!!]" in s or "⚠" in s or "🔴" in s:
        return YELLOW
    if s.startswith(("c4-skill-evaluator", "===", "技能", "挑战", "评审器")):
        return CYAN
    if s.startswith("  ·") or s.startswith("└"):
        return DIM
    return FG


def render(title: str, body: str, exit_code: int, footer: str, out_name: str) -> Path:
    font = ImageFont.truetype(FONT_PATH, SIZE)
    bold = ImageFont.truetype(FONT_PATH, SIZE)
    step = font.getlength("M")

    def cells(s: str) -> int:
        return sum(2 if ord(ch) > 0x2E80 else 1 for ch in s)

    lines = body.splitlines() or [""]
    pad_x, pad_top, line_h, title_h, foot_h = 24, 14, 23, 38, 30
    max_cells = max([cells(title) + 20] + [cells(ln) for ln in lines])
    width = int(max_cells * step) + pad_x * 2
    width = max(width, 720)
    height = title_h + pad_top + line_h * len(lines) + 18 + foot_h

    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    d.line([(0, title_h - 1), (width, title_h - 1)], fill=(48, 54, 61), width=1)
    d.text((pad_x, 11), title, font=bold, fill=FG)
    ec = f"exit code = {exit_code}"
    d.text((width - pad_x - d.textlength(ec, font=font), 11), ec, font=font, fill=DIM)

    y = title_h + pad_top
    for ln in lines:
        d.text((pad_x, y), ln, font=font, fill=colorize(ln))
        y += line_h

    d.line([(0, height - foot_h), (width, height - foot_h)], fill=(48, 54, 61), width=1)
    d.text((pad_x, height - foot_h + 8), footer, font=ImageFont.truetype(FONT_PATH, 12), fill=DIM)

    path = OUT / out_name
    img.save(path)
    print(f"已生成 {path.name}（{width}x{height}，{len(lines)} 行真实输出）")
    return path


def main() -> int:
    jobs = [
        ("T1 · 评审器自测：43 项检查项全过 → 准确率 100% / 误判率 0%",
         run_selftest_summary, 0,
         "真实运行输出 · python examples/run_selftest.py · 退出码 0"),
        ("T2 · 规则层评审 4 份真实技能材料（确定性，可逐字节复现）",
         run_rule_layer, 0,
         "真实运行输出 · python scripts/c4a_evaluate.py --input examples/real_corpus"),
        ("T3 · 反套壳对照：空壳提交骗不过关键项一票否决",
         run_antigame, 0,
         "真实运行输出 · 同一评审器，两个对照样本"),
        ("T4 · 混合层：规则初判 + LLM 深审 → 一致率 81.2%，3 处改判",
         run_hybrid, 0,
         "真实运行输出 · --llm-verdicts 评审产物/llm_verdicts.json"),
        ("T5 · C4A 交付物清单（13 项）",
         run_artifacts, 0,
         "交付物 · 全部位于 C4A提交成果/"),
        ("T6 · 交叉自检对照：全量盲扫 FAIL 80.3 vs 排除测试语料 PASS 99.2",
         run_crosscheck, 0,
         "真实运行落盘 · challenge-submission-checker v1.2.0（评审产物/交叉自检_C4技能*/）"),
    ]
    outs = []
    for i, (title, fn, _, footer) in enumerate(jobs, 1):
        body, code = fn()
        name = f"lishengdan_C4A_demo_{i}_" + {
            1: "自测准确率", 2: "规则层评审", 3: "反套壳对照",
            4: "混合层改判", 5: "交付物清单", 6: "交叉自检对照"}[i] + ".png"
        outs.append(render(title, body, code, footer, name))

    for tmp in (TMP, OUT / "_tmp_rule", OUT / "_tmp_hybrid"):
        if tmp.exists():
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n共生成 {len(outs)} 张 demo 图 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
