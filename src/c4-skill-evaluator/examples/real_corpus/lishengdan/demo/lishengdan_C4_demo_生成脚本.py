# -*- coding: utf-8 -*-
"""
make_demo.py — 生成 C4 提交用的 demo 截图
=========================================

把技能**真实运行**的输出渲染成终端风格 PNG（不是手绘示意图）。

用法（需要 Pillow；本机 D:\\Python3.14.3 已自带）：
    python demo/make_demo.py

产出到 demo/：
    lishengdan_C4_demo_1_技能自测.png
    lishengdan_C4_demo_2_通过场景.png
    lishengdan_C4_demo_3_缺失交付物.png
    lishengdan_C4_demo_4_脏数据与密钥.png
    lishengdan_C4_demo_5_生成报告.png
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent          # C4技能分享/
SKILL = ROOT / "src" / "challenge-submission-checker"
CHECK = SKILL / "scripts" / "check_deliverables.py"
DEMO = ROOT / "demo"
# 中间产物（控制台原始输出、检查报告）放到系统临时目录，
# 不进交付文件夹——否则它们会被下一次自检当成"未按规范命名的交付物"。
RAW = Path(tempfile.mkdtemp(prefix="c4demo_raw_"))
PATTERN = "*skill说明*,*.skill,*教学说明*,*demo*,*AI日志*"

FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"   # 等宽（半角=全角=20px @size20）
FONT_SIZE = 16
LINE_H = 24
PAD_X, PAD_Y = 26, 22
TITLE_H = 46
MAX_CHARS = 118

BG = (13, 17, 23)
FG = (222, 231, 240)
DIM = (108, 122, 137)
GREEN = (80, 210, 130)
RED = (255, 108, 108)
YELLOW = (240, 200, 90)
BLUE = (120, 180, 255)
BAR = (32, 40, 52)
BAR_LINE = (48, 58, 72)


def run(cmd, cwd=SKILL):
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    return p.stdout, p.stderr, p.returncode


def wrap(text, width=MAX_CHARS):
    out = []
    for line in text.splitlines():
        while len(line) > width:
            out.append(line[:width])
            line = "  " + line[width:]
        out.append(line)
    return out


def colorize(line):
    """按内容给整行上色，模拟终端。"""
    s = line.strip()
    if s.startswith(">>>"):
        return GREEN if "PASS" in line and "FAIL" not in line else RED
    if "[OK]" in line:
        return GREEN
    if "[XX]" in line:
        return RED
    if "[!!]" in line:
        return YELLOW
    if s.startswith("challenge-submission-checker"):
        return BLUE
    if s.startswith("###") or s.startswith("==") or s.startswith("--"):
        return DIM
    return FG


def render(lines, title, subtitle=""):
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    bold = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    col_w = font.getlength("M")          # 等宽字体的字符步进
    width = int(col_w * MAX_CHARS) + PAD_X * 2
    height = TITLE_H + LINE_H * len(lines) + PAD_Y * 2

    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    # 顶部标题栏
    d.rectangle([0, 0, width, TITLE_H], fill=(22, 27, 36))
    d.text((PAD_X, 13), title, font=bold, fill=FG)
    if subtitle:
        tw = bold.getlength(subtitle)
        d.text((width - PAD_X - tw, 13), subtitle, font=bold, fill=DIM)

    y = TITLE_H + PAD_Y
    for ln in lines:
        d.text((PAD_X, y), ln, font=font, fill=colorize(ln))
        y += LINE_H

    d.rectangle([0, 0, width - 1, height - 1], outline=BAR_LINE)
    return img


def save(img, name, caption=None):
    if caption:
        d = ImageDraw.Draw(img)
        d.text((PAD_X, img.height - 18), caption, font=ImageFont.truetype(FONT_PATH, 13), fill=DIM)
    out = DEMO / name
    img.save(out)
    print(f"  写出 {out.name}  ({img.width}x{img.height})")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    DEMO.mkdir(exist_ok=True)
    RAW.mkdir(exist_ok=True)
    print("生成 demo 截图 ...")

    # ---- 1. 技能自测套件 ----
    out, err, code = run([sys.executable, "examples/run_selftest.py"])
    (RAW / "selftest.txt").write_text(out, encoding="utf-8")
    save(render(wrap(out), "T1 · 技能自测套件：一条命令验证技能没坏",
                "python examples/run_selftest.py"),
         "lishengdan_C4_demo_1_技能自测.png",
         "真实运行输出 · 对三个固定样例包断言，全部通过")

    # ---- 2/3/4. 三个检查场景 ----
    cases = [
        ("demo-pass", "lishengdan_C4_demo_2_通过场景.png",
         "T2 · 场景A：交付物齐全 → PASS", "齐全的提交"),
        ("demo-missing", "lishengdan_C4_demo_3_缺失交付物.png",
         "T3 · 场景B：缺 2 个交付物 → FAIL 并点名缺什么", "缺失的提交"),
        ("demo-dirty", "lishengdan_C4_demo_4_脏数据与密钥.png",
         "T4 · 场景C：空壳文件 + 假密钥 + 草稿 → FAIL", "脏数据的提交"),
    ]
    for pack, name, title, cap in cases:
        # 注意：检查产物写到 demo/_raw/ 下，绝不写进技能源码目录，
        # 否则打包 .skill 时会把自检产物一起压进去（v1.2 打包时真实踩过的坑）。
        outdir = RAW / f"_check_{pack}"
        args = [sys.executable, str(CHECK), "--pack", f"examples/{pack}",
                "--pattern", PATTERN, "--author", "lishengdan", "--title", "C4 技能分享与传播",
                "--out", str(outdir)]
        out, err, code = run(args)
        (RAW / f"{pack}.txt").write_text(out, encoding="utf-8")
        save(render(wrap(out), title, f"exit code = {code}"),
             name, f"真实运行输出 · {cap} · 退出码 {code}")

    # ---- 5. 生成的 Markdown 报告 ----
    rep = RAW / "_check_demo-pass" / "自检报告.md"
    if rep.exists():
        text = rep.read_text(encoding="utf-8")
        (RAW / "report.md").write_text(text, encoding="utf-8")
        head = "\n".join(text.splitlines()[:34])
        save(render(wrap(head), "T5 · 自动生成的自检报告.md（节选）",
                    "examples/_out_demo-pass/自检报告.md"),
             "lishengdan_C4_demo_5_生成报告.png",
             "三份产物之一 · 另两份为 check_result.json 与 提交清单.md")

    print("完成。")


if __name__ == "__main__":
    main()
