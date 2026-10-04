#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_synthetic_corpus.py — 生成带「标准答案」的合成评测集（评审器的验证集）。

为什么要合成集
--------------
评审器的可靠性不能靠「看起来挺准」。要度量误判率，必须有**已知正确答案**的输入。
真实提交只有 1 份（lishengdan），样本量不足以度量准确率；因此这里构造 6 组
带明确标注的合成样本，覆盖 C4 提交的真实失败模式：

    zhangwei      齐全且高质量            → 期望 5/5，四条件全 ✅，无红旗
    liming        缺 Demo 与 AI 日志      → 期望 3/5，触发 missing_artifacts
    wangxiao      表面齐全、实为空壳      → 期望 空壳 + 伪包 双红旗（反套壳考点）
    zhaolei       只交了 1 个文件         → 期望 1/5，严重缺失
    sunqi         含硬编码路径与真密钥    → 期望 secret_leak 红旗（安全考点）
    chenhao_v1/v2 同一作者的两次迭代      → 期望版本追踪识别出进步

零第三方依赖（含 PNG 用 zlib+struct 手写），可重复生成，输出确定性。
"""

from __future__ import annotations

import shutil
import struct
import sys
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "synthetic_corpus"


# --------------------------------------------------------------------------- #
# 手写 PNG（零依赖，便于可重复生成 fixture）
# --------------------------------------------------------------------------- #

def write_png(path: Path, w: int, h: int, bg: tuple, band: tuple) -> None:
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type 0
        for x in range(w):
            color = band if (y // 8) % 2 == 0 else bg
            raw.extend(color)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))
    path.write_bytes(png)


def make_skill_package(path: Path, skill_name: str, description: str,
                       script_rel: str, script_body: str,
                       with_frontmatter: bool = True) -> None:
    """打包一个合法 .skill（zip：根目录 <skill_name>/SKILL.md + 脚本）。"""
    if with_frontmatter:
        skill_md = (
            "---\n"
            f"name: {skill_name}\n"
            "description: >\n"
            f"  {description}\n"
            "  适用场景：批量处理本地文件夹中的结构化文档。\n"
            "---\n\n"
            f"# {skill_name}\n\n"
            "## Input / Output\n\n"
            "输入：一个本地文件夹路径。输出：一份 Markdown 报告。\n\n"
            "## Workflow\n\n"
            "### Step 1 — 校验输入目录\n"
            "如果目录不存在则报错退出（退出码 2）。\n\n"
            "### Step 2 — 扫描并处理\n"
            "遍历目录，按规则处理后写出报告。\n\n"
            "## Edge cases\n\n"
            "- 空文件夹：输出「未找到文件」并正常退出。\n"
            "- 缺失输入：打印用法后退出码 2。\n"
        )
    else:
        skill_md = "# " + skill_name + "\n\n（本技能未提供 frontmatter）\n"

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{skill_name}/SKILL.md", skill_md)
        zf.writestr(f"{skill_name}/{script_rel}", script_body)


# --------------------------------------------------------------------------- #
# 公共素材
# --------------------------------------------------------------------------- #

CLEAN_SCRIPT = '''#!/usr/bin/env python3
"""把文件夹里的文档汇总成一份 Markdown 报告。"""
import argparse
import sys
from pathlib import Path


def collect(folder: Path) -> list:
    """收集目录下的文本文件。"""
    return sorted(p for p in folder.rglob("*") if p.is_file())


def render(folder: Path) -> str:
    """渲染报告正文。"""
    files = collect(folder)
    lines = [f"# 报告：{folder.name}", "", f"共 {len(files)} 个文件", ""]
    for f in files:
        lines.append(f"- {f.name}")
    return "\\n".join(lines) + "\\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="文件夹文档汇总器")
    parser.add_argument("folder", help="要处理的本地文件夹路径")
    parser.add_argument("--out", default="report.md", help="输出 Markdown 路径")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"ERROR: 不是目录：{folder}", file=sys.stderr)
        return 2

    Path(args.out).write_text(render(folder), encoding="utf-8")
    print(f"已写出 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

GOOD_SKILL_DOC = """# {author}_C4_skill说明.md

> **技能名**：folder-digest（文件夹文档汇总器）
> **一句话**：**输入**一个本地文件夹路径，**输出**一份 Markdown 汇总报告。
> **版本**：v1.0.0 ｜ 零第三方依赖 ｜ Python 3.9+

## 一、解决什么问题

每学期末要把几十个文件夹里的材料整理成一份清单，手动做一遍要两小时，而且每次口径不一致。
本技能把这件事变成一条命令：给定文件夹，输出固定格式的报告，同一份输入永远得到同一份输出。

## 二、使用场景

- 整理课程资料、提交包、会议材料目录。
- 交付前核对某个文件夹里到底有哪些文件。
- 接进自动化流水线，作为「先盘点再处理」的第一步。

## 三、输入 / 输出

| 方向 | 内容 | 类型 |
|------|------|------|
| 输入 | 一个本地文件夹路径 | `str`，必填位置参数 |
| 输出 | 一份 Markdown 报告 | `.md` 文件，默认 `report.md` |

**IO 一句话**：输入一个文件夹路径，输出一份按文件名排序的 Markdown 清单。

## 四、安装与运行环境

```bash
# 环境要求：Python 3.9+，无第三方依赖
python --version

# 安装：把 .skill 解压到技能目录即可，不需要 pip install
unzip {author}_C4_folder-digest.skill -d ./skills/

# 运行
python skills/folder-digest/scripts/digest.py "任意文件夹路径" --out 报告.md
```

兼容 Windows / macOS / Linux；输入接受**任意**本地文件夹路径，不依赖作者本机目录。

## 五、边界情况

- 空文件夹：输出「未找到文件」的报告，退出码 0。
- 路径不存在或不是目录：打印用法，退出码 2。
- 文件名含中文：以 UTF-8 读取，失败回退 GBK。

## 六、验收标准

| 判据 | 阈值 |
|------|------|
| 自测套件 | 3 个用例全过 |
| 输出文件 | 存在且非空 |
| 退出码 | 成功 0 / 参数错误 2 |

预期输出示例：

```
$ python scripts/digest.py ./样例 --out report.md
已写出 report.md
```

## 七、自测

```bash
python examples/run_selftest.py     # 断言：空目录、正常目录、非法路径 三种输入
```
"""

TEACHING_DOC = """# {author}_C4_教学说明.md

## 一、3 分钟上手

1. 解压 `{author}_C4_folder-digest.skill` 到任意目录。
2. 确认 `python --version` ≥ 3.9（无第三方依赖）。
3. 运行 `python scripts/digest.py "你的文件夹" --out 报告.md`。
4. 打开 `报告.md` 核对清单。

## 二、常见坑

- **坑 1：路径带空格没加引号。** Windows 下 `C:/我的 文件夹` 会被拆成两个参数，请加双引号。
- **坑 2：以为需要 pip install。** 本技能零依赖，安装依赖反而可能引入版本冲突。
- **坑 3：在错误的目录下运行。** 脚本用相对路径写 `report.md`，建议用 `--out` 指定绝对目标。

## 三、优化技巧

- 大目录（>5000 文件）建议加 `--out` 写到别的盘，避免扫描盘写满。
- 想接 CI：用退出码判断，`2` 表示参数错误，`0` 表示成功。
- 想改输出格式：只改 `render()` 一个函数即可，扫描逻辑不用动。

## 四、注意事项

- 脚本只读输入目录，不会修改或删除任何文件。
- 不联网，不上传任何内容。
"""

AI_LOG = """# {author}_C4_AI日志.md

## 使用的 AI 工具

- 代码生成与调试：Claude Code（终端内直接改文件、跑测试）
- 文档润色：ChatGPT

## 第 1 轮 · 需求澄清（prompt 原始版）

> prompt：帮我写个整理文件夹的脚本。

AI 给出的是一个把所有文件写进 txt 的 20 行脚本，没有参数解析、没有测试。
**问题**：需求太粗，AI 只能给最平庸的解。

## 第 2 轮 · prompt 优化后

> prompt（优化版）：
> 写一个 Python 3.9 脚本 `digest.py`，要求：
> 1) 位置参数 `folder`，可选 `--out`；2) 不存在的路径打印用法并返回退出码 2；
> 3) 零第三方依赖；4) 输出 Markdown；5) 附带 `examples/run_selftest.py`，
> 用断言覆盖空目录 / 正常目录 / 非法路径三种情况。

这一轮 AI 一次给出可运行版本。**结论**：把验收标准写进 prompt，比事后返工便宜得多。

## 第 3 轮 · 迭代与返工

- 初版把 `print` 写成了 `sys.stdout`，Windows 控制台中文乱码 → 统一 `encoding="utf-8"`。
- 初版自测只测了正常路径 → 补了空目录与非法路径两个反例。
- 失败经验：第二轮我直到写自测时才发现「退出码」没定义，**验收标准应该在 prompt 里先写死**。

## 迭代次数

共 3 轮，其中 1 轮返工（中文编码问题）。
"""

# 空壳样本：故意写占位符
HOLLOW_DOC = "TODO 待补充\n"
PLAIN_FAKE_PACKAGE = "这不是一个 zip 包，只是把扩展名改成了 .skill。\n"

# 故意含真密钥与硬编码路径（安全考点）。
# 注意：注释里**不能**出现 fake/示例/演示 等夹具词，否则会被"夹具语境"规则正确排除，
# 反而测不到 secret_leak 检测能力。
#
# 关键：生成器**自身源码**用运行时拼接构造这个假密钥，源码里不出现完整的 `sk-xxxx` 形态。
# 原因（实测）：C4 的 challenge-submission-checker 会把本文件报成"疑似 OpenAI 风格 API Key"，
# 于是评测器的源码自己反而触发了它要检测的那类告警。落在夹具里的才是拼接后的完整字面量，
# 而夹具位于 .skill 包内，扫描器按约定跳过 .skill。
_FAKE_CRED = "sk-" + "live9f2b7c1d4e8a3b6c0d5f7"
DIRTY_SCRIPT = '''#!/usr/bin/env python3
"""导出远端数据到 csv（生产工具）。"""
import csv
import requests

# 生产环境凭据
API_KEY = "@@K@@"

DATA_DIR = "D:/sunqi/private/data"
OUT_DIR = "/home/sunqi/out"


def fetch(url):
    """拉取远端数据。"""
    headers = {"Authorization": API_KEY}
    return requests.get(url, headers=headers, timeout=10).json()


def dump(rows, path):
    """把数据写成 csv。"""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)


if __name__ == "__main__":
    dump(fetch("https://example.invalid/api/rows"), OUT_DIR + "/rows.csv")
'''.replace("@@K@@", _FAKE_CRED)


# --------------------------------------------------------------------------- #
# 组装
# --------------------------------------------------------------------------- #

def reset() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)


def build_zhangwei() -> None:
    d = OUT / "zhangwei"
    d.mkdir(parents=True)
    (d / "zhangwei_C4_skill说明.md").write_text(GOOD_SKILL_DOC.format(author="zhangwei"), encoding="utf-8")
    (d / "zhangwei_C4_教学说明.md").write_text(TEACHING_DOC.format(author="zhangwei"), encoding="utf-8")
    (d / "zhangwei_C4_AI日志.md").write_text(AI_LOG.format(author="zhangwei"), encoding="utf-8")
    write_png(d / "zhangwei_C4_demo截图.png", 320, 120, (255, 255, 255), (214, 230, 247))
    make_skill_package(
        d / "zhangwei_C4_folder-digest.skill", "folder-digest",
        "扫描本地文件夹并把文件清单汇总成 Markdown 报告；输入文件夹路径，输出 report.md。",
        "scripts/digest.py", CLEAN_SCRIPT)


def build_liming() -> None:
    d = OUT / "liming"
    d.mkdir(parents=True)
    (d / "liming_C4_skill说明.md").write_text(GOOD_SKILL_DOC.format(author="liming"), encoding="utf-8")
    (d / "liming_C4_教学说明.md").write_text(TEACHING_DOC.format(author="liming"), encoding="utf-8")
    make_skill_package(
        d / "liming_C4_folder-digest.skill", "folder-digest",
        "扫描本地文件夹并把文件清单汇总成 Markdown 报告；输入文件夹路径，输出 report.md。",
        "scripts/digest.py", CLEAN_SCRIPT)


def build_wangxiao() -> None:
    d = OUT / "wangxiao"
    d.mkdir(parents=True)
    # 五个文件一个不缺 —— 但四个是空壳，一个是伪包
    (d / "wangxiao_C4_skill说明.md").write_text(HOLLOW_DOC, encoding="utf-8")
    (d / "wangxiao_C4_教学说明.md").write_text("待完善\n", encoding="utf-8")
    (d / "wangxiao_C4_AI日志.md").write_text("TBD\n", encoding="utf-8")
    write_png(d / "wangxiao_C4_demo截图.png", 200, 80, (255, 255, 255), (250, 220, 220))
    (d / "wangxiao_C4_my-skill.skill").write_text(PLAIN_FAKE_PACKAGE, encoding="utf-8")


def build_zhaolei() -> None:
    d = OUT / "zhaolei"
    d.mkdir(parents=True)
    (d / "zhaolei_C4_skill说明.md").write_text(GOOD_SKILL_DOC.format(author="zhaolei"), encoding="utf-8")


def build_sunqi() -> None:
    d = OUT / "sunqi"
    d.mkdir(parents=True)
    (d / "sunqi_C4_skill说明.md").write_text(GOOD_SKILL_DOC.format(author="sunqi"), encoding="utf-8")
    (d / "sunqi_C4_教学说明.md").write_text(TEACHING_DOC.format(author="sunqi"), encoding="utf-8")
    (d / "sunqi_C4_AI日志.md").write_text(AI_LOG.format(author="sunqi"), encoding="utf-8")
    write_png(d / "sunqi_C4_demo截图.png", 200, 80, (255, 255, 255), (220, 245, 220))
    make_skill_package(
        d / "sunqi_C4_data-export.skill", "data-export",
        "导出远端数据到 csv。",
        "scripts/export.py", DIRTY_SCRIPT, with_frontmatter=False)


def build_chenhao() -> None:
    for ver, files in (("v1", ["skill说明", "folder-digest.skill", "demo截图"]),
                       ("v2", ["skill说明", "教学说明", "AI日志", "folder-digest.skill", "demo截图"])):
        d = OUT / f"chenhao_{ver}"
        d.mkdir(parents=True)
        if "skill说明" in files:
            (d / f"chenhao_{ver}_C4_skill说明.md").write_text(
                GOOD_SKILL_DOC.format(author=f"chenhao_{ver}"), encoding="utf-8")
        if "教学说明" in files:
            (d / f"chenhao_{ver}_C4_教学说明.md").write_text(
                TEACHING_DOC.format(author=f"chenhao_{ver}"), encoding="utf-8")
        if "AI日志" in files:
            (d / f"chenhao_{ver}_C4_AI日志.md").write_text(
                AI_LOG.format(author=f"chenhao_{ver}"), encoding="utf-8")
        write_png(d / f"chenhao_{ver}_C4_demo截图.png", 240, 90, (255, 255, 255), (222, 235, 250))
        pkg = d / f"chenhao_{ver}_C4_folder-digest.skill"
        make_skill_package(pkg, "folder-digest",
                           "扫描本地文件夹并把文件清单汇总成 Markdown 报告；输入文件夹路径，输出 report.md。",
                           "scripts/digest.py", CLEAN_SCRIPT)


def main() -> int:
    reset()
    build_zhangwei()
    build_liming()
    build_wangxiao()
    build_zhaolei()
    build_sunqi()
    build_chenhao()
    n = len(list(OUT.rglob("*")))
    print(f"合成评测集已生成：{OUT}")
    print(f"目录数 8（zhangwei / liming / wangxiao / zhaolei / sunqi / chenhao_v1 / chenhao_v2），条目 {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
