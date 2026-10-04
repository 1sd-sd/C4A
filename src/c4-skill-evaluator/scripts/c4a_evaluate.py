#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
c4a_evaluate.py — C4A 技能提交自动评审器（Level 1–4 完整实现）

一句话 IO：输入一个装着 C4 提交的本地文件夹路径，输出「谁交了什么 / 齐不齐 / 好不好 /
下一步改什么」的评审报告（Markdown + CSV + HTML）与机器可读 JSON。

设计要点
--------
* 零第三方依赖：只用标准库（json / re / zipfile / tarfile / csv / html / pathlib）。
* 配置驱动：所有信号、权重、阈值都写在 references/c4a_rubric.json，本文件不含评审硬编码。
* 规则 + LLM 混合：规则给出确定性初判与证据；可用 --emit-llm-prompt 生成深审 prompt，
  再用 --llm-verdicts 回灌 LLM 结论，两者在报告中分别标注来源并可算一致率。
* 反套壳（claim-vs-reality）：.skill 是否真能解压、SKILL.md 是否真有 frontmatter、
  代码是否真能 compile()、文档声称的脚本是否真存在 —— 一律实测，不信关键词。
* N/A 机制：不适用项（如无 SKILL.md 时的 frontmatter 检查）不计入分母，避免无谓扣分。

Usage
-----
    python scripts/c4a_evaluate.py --input <提交文件夹> [--outdir <输出目录>]
        [--profile c4_four_conditions|platform_100] [--challenge C4]
        [--exclude <目录> ...] [--prefix lishengdan_C4A]
        [--emit-llm-prompt] [--llm-verdicts verdicts.json] [--quiet-json]

退出码：0 = 正常；2 = 存在高严重度红旗（可用作 CI 卡点）。
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import os
import re
import sys
import tarfile
import unicodedata
import zipfile
from collections import defaultdict, OrderedDict
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# 0. 基础设施
# --------------------------------------------------------------------------- #

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    pass

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RUBRIC = SKILL_DIR / "references" / "c4a_rubric.json"

RATING_SYMBOL = {"pass": "✅", "partial": "⚠️", "fail": "❌", "na": "—"}
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_rubric(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_slug(name: str) -> str:
    """把作者名清洗成可安全用作文件名的片段。"""
    name = unicodedata.normalize("NFKC", name).strip()
    name = re.sub(r"[\\/:*?\"<>|\s]+", "_", name)
    return name or "unknown"


# --------------------------------------------------------------------------- #
# 1. Level 1 — 文件采集与识别
# --------------------------------------------------------------------------- #

def _is_junk(name: str, rubric: dict) -> bool:
    for pat in rubric["scan"]["junk_name_patterns"]:
        if re.search(pat, name):
            return True
    return False


def scan_folder(root: Path, rubric: dict, excludes: list[Path]) -> list[dict]:
    """递归扫描，产出文件信息列表（Level 1 的原始输入）。"""
    skip_dirs = set(rubric["scan"]["skip_dir_names"])
    max_bytes = rubric["scan"]["max_content_bytes"]
    files: list[dict] = []

    for path in sorted(root.rglob("*")):
        try:
            if not path.is_file():
                continue
        except OSError:
            continue

        try:
            rel = path.relative_to(root)
        except ValueError:
            continue

        if any(part in skip_dirs for part in rel.parts[:-1]):
            continue
        if any(part in skip_dirs for part in rel.parts):
            continue

        skip = False
        for ex in excludes:
            try:
                path.relative_to(ex)
                skip = True
                break
            except ValueError:
                pass
        if skip:
            continue

        name = path.name
        if name.startswith(".") and name not in (".gitignore", ".gitattributes"):
            continue

        try:
            st = path.stat()
        except OSError:
            continue

        ext = path.suffix.lower()
        if name.lower().endswith(".tar.gz"):
            ext = ".tar.gz"

        files.append({
            "rel": rel.as_posix(),
            "name": name,
            "stem": path.stem,
            "ext": ext,
            "size": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"),
            "abs": str(path),
            "junk": _is_junk(name, rubric),
            "oversize": st.st_size > max_bytes,
        })
    return files


def extract_author_from_name(stem: str, rubric: dict) -> dict | None:
    pat = re.compile(rubric["naming"]["filename_pattern"])
    m = pat.match(stem)
    if not m:
        return None
    author = m.group("author").strip()
    if author.lower() in {a.lower() for a in rubric["naming"]["author_blacklist"]}:
        return None
    return {"author": author, "challenge": m.group("challenge"), "part": m.group("part"),
            "source": "filename", "convention_match": True}


def extract_author_from_docx_meta(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as zf:
            for member in ("docProps/core.xml", "docProps/app.xml"):
                if member in zf.namelist():
                    raw = zf.read(member).decode("utf-8", "replace")
                    m = re.search(r"<dc:creator>(.*?)</dc:creator>", raw)
                    if m and m.group(1).strip():
                        return m.group(1).strip()
    except Exception:
        return None
    return None


def extract_author_from_header(text: str) -> str | None:
    for line in (text or "").splitlines()[:12]:
        m = re.search(r"(?:姓名|作者|author|name)\s*[:：]\s*([A-Za-z\u4e00-\u9fa5_\-]{2,32})", line, re.I)
        if m:
            return m.group(1).strip()
    return None


def resolve_author(fi: dict, root: Path, text_cache: dict, rubric: dict) -> dict:
    """作者识别链：文件名 → 目录名 → 文档头 → 文档元数据 → Unknown。"""
    parsed = extract_author_from_name(fi["stem"], rubric)
    if parsed:
        return parsed

    rel_parts = fi["rel"].split("/")
    if len(rel_parts) >= 2:
        folder = rel_parts[0]
        if folder not in {"", "."}:
            return {"author": folder, "challenge": None, "part": fi["stem"],
                    "source": "folder", "convention_match": False}

    header = extract_author_from_header(text_cache.get(fi["abs"], ""))
    if header:
        return {"author": header, "challenge": None, "part": fi["stem"],
                "source": "content", "convention_match": False}

    if fi["ext"] == ".docx":
        meta = extract_author_from_docx_meta(Path(fi["abs"]))
        if meta:
            return {"author": meta, "challenge": None, "part": fi["stem"],
                    "source": "metadata", "convention_match": False}

    return {"author": "Unknown", "challenge": None, "part": fi["stem"],
            "source": "fallback", "convention_match": False}


def split_version(stem: str, author: str, rubric: dict) -> tuple[str, int | None]:
    """识别 _v2 / _v3 迭代版本，返回 (base_author, version)。"""
    ver = None
    base = author
    m = re.search(rubric["naming"]["version_pattern"], author)
    if m:
        ver = int(m.group("ver"))
        base = m.group("base")
    else:
        m2 = re.search(rubric["naming"]["version_in_part"], stem)
        if m2:
            ver = int(m2.group(1))
    base = re.sub(r"[_\-][vV]\d+$", "", base)
    return base, ver


# --------------------------------------------------------------------------- #
# 2. 内容读取（零依赖）
# --------------------------------------------------------------------------- #

def read_text_file(path: Path, limit: int) -> str:
    try:
        raw = path.read_bytes()[:limit]
    except OSError:
        return ""
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def read_docx_text(path: Path, limit: int) -> str:
    """从 .docx（zip）里抽出正文纯文本，零依赖。"""
    try:
        with zipfile.ZipFile(path) as zf:
            if "word/document.xml" not in zf.namelist():
                return ""
            xml = zf.read("word/document.xml")[: limit * 8].decode("utf-8", "replace")
    except Exception:
        return ""
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(xml)[:limit]


def archive_members(path: Path) -> tuple[str, list[str], dict]:
    """返回 (格式, 成员名列表, {成员名: 文本})。格式 ∈ zip / tar / unknown。"""
    names: list[str] = []
    texts: dict[str, str] = {}
    try:
        head = path.read_bytes()[:4]
    except OSError:
        return "unknown", names, texts

    text_exts = {".md", ".txt", ".py", ".sh", ".js", ".json", ".yaml", ".yml", ".csv", ".tex", ".html", ".cfg", ".toml", ".ini"}

    if head[:2] == b"PK":
        try:
            with zipfile.ZipFile(path) as zf:
                for info in zf.infolist():
                    names.append(info.filename)
                    if Path(info.filename).suffix.lower() in text_exts and info.file_size < 512 * 1024:
                        try:
                            texts[info.filename] = zf.read(info).decode("utf-8", "replace")
                        except Exception:
                            pass
            return "zip", names, texts
        except Exception:
            return "zip-broken", names, texts

    if head[:2] == b"\x1f\x8b":
        try:
            with tarfile.open(path, "r:gz") as tf:
                for member in tf.getmembers():
                    names.append(member.name)
                    if member.isfile() and Path(member.name).suffix.lower() in text_exts and member.size < 512 * 1024:
                        fh = tf.extractfile(member)
                        if fh:
                            texts[member.name] = fh.read().decode("utf-8", "replace")
            return "tar", names, texts
        except Exception:
            return "tar-broken", names, texts

    return "unknown", names, texts


def parse_frontmatter(text: str) -> dict | None:
    """解析 SKILL.md 的 YAML frontmatter（支持 > / | 块标量，零依赖）。"""
    if not text:
        return None
    m = re.match(r"^\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.S)
    if not m:
        return None

    fm: dict[str, str] = {}
    key = None
    buf: list[str] = []

    def flush() -> None:
        if key:
            fm[key] = " ".join(x.strip() for x in buf if x.strip()).strip()

    for line in m.group(1).splitlines():
        if re.match(r"^\s*#", line):
            continue
        if line[:1] in (" ", "\t"):
            if key is not None:
                buf.append(line)
            continue
        mm = re.match(r"^([A-Za-z_][\w\-]*)\s*:\s*(.*)$", line)
        if mm:
            flush()
            key = mm.group(1).lower()
            val = mm.group(2).strip()
            # 块标量（> | >- |- >+ |+ <）的值在后续缩进行里
            buf = [] if re.match(r"^[>|][+-]?$", val) else [val]
        else:
            flush()
            key, buf = None, []
    flush()
    return fm


# --------------------------------------------------------------------------- #
# 3. Level 2 — 提交完整性检查
# --------------------------------------------------------------------------- #

def build_content_index(files: list[dict], rubric: dict) -> dict:
    """为每个文件预备「可搜索文本」，供匹配与质量检查复用。"""
    limit = rubric["scan"]["max_content_bytes"]
    text_kinds = set(rubric["file_kinds"]["text"])
    docx_kinds = set(rubric["file_kinds"]["docx"])
    archive_kinds = set(rubric["file_kinds"]["archive"])

    cache: dict[str, str] = {}
    pkg: dict[str, dict] = {}

    for fi in files:
        ext = fi["ext"]
        if fi["oversize"]:
            cache[fi["abs"]] = ""
            continue
        if ext in text_kinds:
            cache[fi["abs"]] = read_text_file(Path(fi["abs"]), limit)
        elif ext in docx_kinds:
            cache[fi["abs"]] = read_docx_text(Path(fi["abs"]), limit)
        elif ext in archive_kinds:
            fmt, names, texts = archive_members(Path(fi["abs"]))
            pkg[fi["abs"]] = {"format": fmt, "names": names, "texts": texts}
            # 归档内的文本也参与内容匹配（否则「把代码藏进 zip」可以绕过检查）
            cache[fi["abs"]] = "\n".join(texts.values())[:limit]
        else:
            cache[fi["abs"]] = ""
    return {"text": cache, "pkg": pkg}


def score_pair(deliv_key: str, cfg: dict, fi: dict, content: dict, rubric: dict) -> tuple[float, list[str]]:
    """给「交付物槽位 × 文件」打分。

    accept_ext 是**硬过滤**：扩展名不在白名单里的文件完全不可能命中该槽位。
    没有这一层，规则文件（如 rubric.yaml 里恰好写着「输入」「输出」这些信号词）
    会被误判成「Skill 说明文档」——这是「匹配到了规范本身」的经典假阳性。

    strong_ext 是**强证据扩展名**：`.skill` / `.py` / `.zip` 这类文件本身在语义上
    就是"可执行内容"，即使文件名没有命中信号，也应判定为强匹配。
    """
    mw = rubric["match_weights"]
    if fi["ext"] not in cfg["accept_ext"]:
        return 0.0, []

    score = 0.0
    ev: list[str] = []
    stem_low = fi["stem"].lower()

    for sig in cfg["filename_signals"]:
        if sig.lower() in stem_low:
            score += mw["filename_signal"]
            ev.append(f"文件名命中「{sig}」")
    score += mw["extension"]

    text = content["text"].get(fi["abs"], "")
    if text and cfg["content_signals"]:
        hits = [s for s in cfg["content_signals"] if s.lower() in text.lower()]
        if hits:
            score += min(len(hits) * mw["content_signal"], mw["content_signal_cap"])
            ev.append("内容命中 " + "、".join(f"「{h}」" for h in hits[:4]))

    if fi["ext"] in cfg.get("strong_ext", []) and score > 0:
        score = max(score, mw["strong_threshold"])
        ev.append(f"扩展名 {fi['ext']} 属强证据类型")
    return score, ev


def check_completeness(author_files: list[dict], content: dict, rubric: dict) -> dict:
    """贪心分配：每个文件只归属一个交付物槽位，避免一个文件被重复计分。"""
    mw = rubric["match_weights"]
    deliverables = rubric["required_deliverables"]

    pairs = []
    for fi in author_files:
        if fi["junk"]:
            continue
        for dk, cfg in deliverables.items():
            sc, ev = score_pair(dk, cfg, fi, content, rubric)
            if sc > 0:
                pairs.append((sc, dk, fi, ev))
    pairs.sort(key=lambda x: (-x[0], x[2]["rel"]))

    assigned_files: set[str] = set()
    slots: dict[str, list[dict]] = {dk: [] for dk in deliverables}

    for sc, dk, fi, ev in pairs:
        if fi["abs"] in assigned_files:
            continue
        assigned_files.add(fi["abs"])
        level = "strong" if sc >= mw["strong_threshold"] else ("weak" if sc >= mw["weak_threshold"] else "none")
        if level == "none":
            continue
        slots[dk].append({"file": fi, "score": round(sc, 2), "level": level, "evidence": ev})

    result = {"slots": {}, "score": 0.0, "present": 0, "hollow": []}
    for dk, cfg in deliverables.items():
        entries = sorted(slots[dk], key=lambda e: -e["score"])
        best = entries[0] if entries else None
        status = "❌"
        hollow = False
        if best:
            if best["file"]["size"] < mw["hollow_bytes"]:
                status = "⚠️"
                hollow = True
                result["hollow"].append(best["file"]["rel"])
            elif best["level"] == "strong":
                status = "✅"
            else:
                status = "⚠️"
        if status == "✅":
            result["present"] += 1
            result["score"] += cfg["weight"]
        elif status == "⚠️":
            result["score"] += cfg["weight"] * 0.5
        result["slots"][dk] = {
            "label": cfg["label"],
            "weight": cfg["weight"],
            "status": status,
            "hollow": hollow,
            "matched": [e["file"]["rel"] for e in entries],
            "best": best["file"]["rel"] if best else None,
            "evidence": best["evidence"] if best else [],
            "level": best["level"] if best else "none",
        }

    ratio = result["score"]
    bands = rubric["scoring"]["completeness_bands"]
    if ratio >= bands["complete"]["min_ratio"]:
        band = bands["complete"]
    elif ratio >= bands["partial"]["min_ratio"]:
        band = bands["partial"]
    else:
        band = bands["insufficient"]
    result["ratio"] = round(ratio, 4)
    result["band"] = band["cn"]
    result["band_symbol"] = band["symbol"]
    extra = [f for f in author_files
             if f["abs"] not in assigned_files and not f["junk"] and f["rel"] not in
             [e for s in slots.values() for e in [x["file"]["rel"] for x in s]]]
    result["extra_files"] = [f["rel"] for f in extra]
    result["junk_files"] = [f["rel"] for f in author_files if f["junk"]]
    return result


# --------------------------------------------------------------------------- #
# 4. Level 3 — 质量评审（四条件 / 平台维度）
# --------------------------------------------------------------------------- #

def collect_samples(author_files: list[dict], content: dict, rubric: dict) -> dict:
    """把该提交的全部素材分成：文档文本（doc）、代码文本（code）、归档（pkg）。

    doc 与 code 严格分离（避免用「文档里出现绝对路径」的阈值去数代码里的路径），
    all = doc + code，只用于关键词检索。
    """
    text_kinds = set(rubric["file_kinds"]["text"])
    docx_kinds = set(rubric["file_kinds"]["docx"])
    archive_kinds = set(rubric["file_kinds"]["archive"])
    code_exts = {".py", ".sh", ".js", ".mjs", ".ts", ".c", ".cpp", ".java", ".go", ".rs", ".r"}
    code_exts |= {".py", ".sh", ".bash"}

    doc: list[tuple[str, str]] = []
    code: list[tuple[str, str]] = []
    pkgs: list[dict] = []

    for fi in author_files:
        if fi["junk"] or fi["oversize"]:
            continue
        ext = fi["ext"]
        text = content["text"].get(fi["abs"], "")
        if ext in archive_kinds:
            info = content["pkg"].get(fi["abs"], {"format": "unknown", "names": [], "texts": {}})
            pkgs.append({"file": fi, **info})
            for name, body in info["texts"].items():
                origin = f"{fi['name']}::{name}"
                if Path(name).suffix.lower() in code_exts:
                    code.append((origin, body))
                elif Path(name).suffix.lower() in {".md", ".txt", ".yaml", ".yml", ".json", ".html"}:
                    doc.append((origin, body))
        elif ext in code_exts:
            code.append((fi["rel"], text))
        elif ext in text_kinds:
            doc.append((fi["rel"], text))
        elif ext in docx_kinds:
            doc.append((fi["rel"], text))
    return {"doc": doc, "code": code, "all": doc + code, "pkgs": pkgs}


def _haystack(samples: dict) -> str:
    return "\n".join(t for _, t in samples["all"]).lower()


def _code_haystack(samples: dict) -> str:
    return "\n".join(t for _, t in samples["code"])


def _any_keyword(words: list[str], samples: dict) -> tuple[bool, list[str]]:
    hay = _haystack(samples)
    hits = [w for w in words if w.lower() in hay]
    return bool(hits), hits[:4]


def _any_file_token(tokens: list[str], samples: dict, files: list[dict]) -> tuple[bool, list[str]]:
    hits = []
    for tok in tokens:
        for fi in files:
            if tok.lower() in fi["stem"].lower():
                hits.append(fi["rel"])
                break
    return bool(hits), hits[:3]


def eval_item(item: dict, samples: dict, files: list[dict], rubric: dict) -> dict:
    """执行单条检查项，返回 {id, check, status(pass|partial|fail|na), evidence, fix}。"""
    rule = item["rule"]
    out = {"id": item["id"], "check": item["check"], "status": "na", "evidence": [],
           "critical": bool(item.get("critical")), "fix": item.get("fix", "")}

    if rule == "keyword":
        ok, hits = _any_keyword(item.get("any_of", []), samples)
        out["status"] = "pass" if ok else "fail"
        if hits:
            out["evidence"] = [f"命中关键词：{'、'.join('「'+h+'」' for h in hits)}"]

    elif rule == "regex":
        pat = re.compile(item["pattern"], re.I)
        # reject_if：命中片段里若含规范/模板占位符（如 ".*"、"___"、"<X>"），说明这是
        # 一条「规则说明」而不是提交者自己的 IO 声明，必须跳过，否则会匹配到规范本身。
        reject = [t for t in item.get("reject_if", []) if t]
        found = False
        for origin, text in samples["doc"]:
            for m in pat.finditer(text):
                frag = m.group(0)
                if any(t in frag for t in reject):
                    continue
                out["status"] = "pass"
                out["evidence"] = [f"{origin}：…{frag[:60]}…"]
                found = True
                break
            if found:
                break
        if not found:
            out["status"] = "fail"

    elif rule == "keyword_or_file":
        ok, hits = _any_keyword(item.get("any_of", []), samples)
        ev = [f"命中关键词：{'、'.join('「'+h+'」' for h in hits)}"] if hits else []
        if ok:
            out["status"] = "pass"
        else:
            fok, fhits = _any_file_token(item.get("file_name_any", []), samples, files)
            out["status"] = "pass" if fok else "fail"
            ev = [f"存在文件：{'、'.join(fhits)}"] if fok else []
        out["evidence"] = ev

    elif rule == "keyword_or_determinism":
        ok, hits = _any_keyword(item.get("any_of", []), samples)
        if ok:
            out["status"] = "pass"
            out["evidence"] = [f"命中关键词：{'、'.join('「'+h+'」' for h in hits)}"]
        else:
            # 规则驱动脚本在构造上就是确定性的：无随机数即视为通过
            code_text = _code_haystack(samples)
            deterministic = bool(samples["code"]) and not re.search(r"\b(random|shuffle|uuid4|np\.random)\b", code_text)
            out["status"] = "partial" if deterministic else "fail"
            if deterministic:
                out["evidence"] = ["代码未使用随机源，且规则驱动 → 同输入同输出"]

    elif rule == "forbidden_in_code":
        pat = re.compile(item["pattern"])
        hits = []
        for origin, text in samples["code"]:
            for m in pat.finditer(text):
                hits.append(f"{origin}: {m.group(0)}")
        if not samples["code"]:
            out["status"] = "na"
        elif not hits:
            out["status"] = "pass"
            out["evidence"] = ["可执行文件中未发现硬编码绝对路径"]
        else:
            out["status"] = "fail"
            out["evidence"] = hits[:5]

    elif rule == "forbidden_in_doc":
        pat = re.compile(item["pattern"])
        hits = []
        for origin, text in samples["doc"]:
            for m in pat.finditer(text):
                hits.append(f"{origin}: {m.group(0)}")
        pass_n = item.get("max_allow", 4)
        mid_n = item.get("max_allow_partial", pass_n * 5)
        if not hits:
            out["status"] = "pass"
            out["evidence"] = ["文档中未发现硬编码绝对路径"]
        elif len(hits) <= pass_n:
            out["status"] = "pass"
            out["evidence"] = [f"文档出现 {len(hits)} 处示例路径（≤{pass_n}，视为示例）"] + hits[:3]
        elif len(hits) <= mid_n:
            out["status"] = "partial"
            out["evidence"] = [f"文档出现 {len(hits)} 处绝对路径（阈值 {pass_n}），与本机目录耦合偏重"] + hits[:3]
        else:
            out["status"] = "fail"
            out["evidence"] = [f"文档出现 {len(hits)} 处硬编码路径（远超阈值 {mid_n}）"] + hits[:5]

    elif rule == "executable_present":
        has_code = bool(samples["code"])
        ok, hits = _any_keyword(item.get("any_of", []), samples)
        has_workflow = bool(re.search(r"(?im)^#{2,4}\s*(workflow|工作流|步骤|pipeline|流程)", _haystack(samples)))
        if has_code or has_workflow:
            out["status"] = "pass"
            if has_code:
                out["evidence"] = [f"包含 {len(samples['code'])} 个代码文件/代码段"]
            else:
                out["evidence"] = ["SKILL.md 内含有序工作流/步骤章节"]
        elif ok:
            out["status"] = "partial"
            out["evidence"] = [f"仅有描述性代码痕迹：{'、'.join(hits)}"]
        else:
            out["status"] = "fail"

    elif rule == "package_valid":
        if not samples["pkgs"]:
            out["status"] = "na"
            out["evidence"] = ["未提交 .skill / 压缩包"]
        else:
            good, bad = [], []
            for pk in samples["pkgs"]:
                fmt = pk["format"]
                has_skill = any(Path(n).name.upper() == "SKILL.MD" for n in pk["names"])
                if fmt in ("zip", "tar") and has_skill:
                    good.append(f"{pk['file']['name']}：{fmt} 格式、{len(pk['names'])} 个条目、含 SKILL.md")
                elif fmt in ("zip-broken", "tar-broken", "unknown"):
                    bad.append(f"{pk['file']['name']}：压缩包无法解析（{fmt}）")
                else:
                    bad.append(f"{pk['file']['name']}：可以解压但缺少 SKILL.md")
            if good and not bad:
                out["status"] = "pass"
            elif good:
                out["status"] = "partial"
            else:
                out["status"] = "fail"
            out["evidence"] = good + bad

    elif rule == "python_syntax":
        pylike = [(o, t) for o, t in samples["code"] if o.endswith(".py") or "::" in o and o.endswith(".py")]
        if not pylike:
            out["status"] = "na"
            out["evidence"] = ["未包含 Python 源码"]
        else:
            bad = []
            ok_n = 0
            for origin, text in pylike:
                try:
                    compile(text, origin, "exec")
                    ok_n += 1
                except SyntaxError as exc:
                    bad.append(f"{origin}:{exc.lineno} {exc.msg}")
            if not bad:
                out["status"] = "pass"
                out["evidence"] = [f"{ok_n} 个 Python 文件 compile() 通过"]
            else:
                out["status"] = "fail"
                out["evidence"] = bad[:4]

    elif rule == "frontmatter":
        # 同时覆盖「散装 SKILL.md」与「.skill 包内的 SKILL.md」两种形态
        candidates = [(o, t) for o, t in samples["doc"]
                      if Path(o.split("::")[-1]).name.upper() == "SKILL.MD"]
        if not candidates:
            out["status"] = "na"
            out["evidence"] = ["未提交 SKILL.md"]
        else:
            bad = []
            for origin, text in candidates:
                fm = parse_frontmatter(text)
                if not fm:
                    bad.append(f"{origin}：缺少 frontmatter")
                elif not fm.get("name"):
                    bad.append(f"{origin}：frontmatter 缺 name")
                elif len(fm.get("description", "")) < 20:
                    bad.append(f"{origin}：description 过短（{len(fm.get('description', ''))} 字符），技能难以被触发")
                else:
                    out["evidence"].append(
                        f"{origin}：name={fm['name']}，description {len(fm['description'])} 字符")
            out["status"] = "pass" if not bad else "fail"
            out["evidence"] += bad

    elif rule == "deliverable_nonempty":
        key = item["deliverable"]
        matched = [fi for fi in files if key in fi["rel"].lower() or key in fi["stem"].lower()]
        if not matched:
            out["status"] = "fail"
            out["evidence"] = ["未找到 demo 文件"]
        else:
            nonempty = [fi for fi in matched if fi["size"] >= rubric["match_weights"]["hollow_bytes"]]
            if nonempty:
                out["status"] = "pass"
                out["evidence"] = [f"{fi['rel']}（{fi['size'] / 1024:.1f} KB）" for fi in nonempty[:3]]
            else:
                out["status"] = "fail"
                out["evidence"] = ["demo 文件存在但为空/过小"]

    elif rule == "no_hollow":
        hollows = [fi for fi in files if fi["size"] == 0 and not fi["junk"]]
        placeholders = []
        pat = re.compile("|".join(rubric["hollow_patterns"]), re.I | re.M)
        guard = rubric.get("fixture_guard", {})
        fix_re = re.compile(guard.get("path_re", r"$^"))
        for origin, text in samples["doc"]:
            if fix_re.search(origin.split("::")[-1]):
                continue
            if pat.search(text) and len(text.strip()) < 400:
                placeholders.append(origin)
        if not hollows and not placeholders:
            out["status"] = "pass"
            out["evidence"] = ["未发现空文件或占位符文件"]
        else:
            out["status"] = "fail"
            out["evidence"] = [f"0 字节文件：{f['rel']}" for f in hollows[:3]] + [f"占位符文件：{p}" for p in placeholders[:3]]

    else:  # pragma: no cover
        out["status"] = "na"
        out["evidence"] = [f"未知规则 {rule}"]

    return out


def _mask_secret(token: str) -> str:
    """报告里**永不**原样复现密钥样式的字符串。

    即使是测试夹具里的假密钥，把完整字面量写进报告也是坏习惯：
    ① 会被下游的密钥扫描器再次命中（本评审器做交叉自检时实测发生）；
    ② 养成"报告可以含凭据"的习惯，迟早会漏真凭据。
    保留首尾各 4 位，足以定位与核对，又不构成可用凭据。
    """
    token = token.strip()
    if len(token) <= 12:
        return token[:3] + "…(已脱敏)"
    return f"{token[:8]}…{token[-4:]}(已脱敏)"


def detect_red_flags(files: list[dict], samples: dict, completeness: dict, rubric: dict) -> list[dict]:
    flags = []
    secrets = []
    fixture_secrets = []
    guard = rubric.get("fixture_guard", {})
    path_re = re.compile(guard.get("path_re", r"$^"))
    ctx_re = re.compile(guard.get("context_re", r"$^"))

    # 逐条编译：单条模式自带 (?i) 时不能简单用 | 拼接（内联 flag 必须位于表达式开头）
    sec_pats = []
    for raw in rubric["secret_patterns"]:
        try:
            sec_pats.append(re.compile(raw))
        except re.error:
            pass
    for origin, text in samples["doc"] + samples["code"]:
        member_path = origin.split("::")[-1]
        in_fixture = bool(path_re.search(member_path))
        for pat in sec_pats:
            for m in pat.finditer(text):
                ctx = text[max(0, m.start() - 90): m.end() + 90]
                shown = _mask_secret(m.group(0))
                if in_fixture or ctx_re.search(ctx):
                    fixture_secrets.append(f"{origin}: {shown}")
                else:
                    secrets.append(f"{origin}: {shown}")
    if secrets:
        flags.append({"id": "secret_leak", "cn": "疑似敏感信息泄露", "severity": "critical", "evidence": secrets[:3]})
    if fixture_secrets:
        flags.append({"id": "secret_fixture_ignored", "cn": "已排除测试夹具中的假密钥（透明记录，不扣分）",
                      "severity": "info", "evidence": [f"共 {len(fixture_secrets)} 处"] + fixture_secrets[:2]})

    # 「缺失」包含两类：整类无文件（❌），以及唯一命中的文件是空壳（⚠️ 且 hollow）
    # —— 只交了占位符，等于没交。
    missing = [k for k, v in completeness["slots"].items()
               if v["status"] == "❌" or v.get("hollow")]
    if len(missing) >= 2:
        flags.append({"id": "missing_artifacts", "cn": "核心交付物缺失",
                      "severity": "high", "evidence": [completeness["slots"][k]["label"] for k in missing]})

    if "ai_log" in missing:
        flags.append({"id": "no_ai_log", "cn": "无 AI 使用记录", "severity": "high", "evidence": []})
    if "demo" in missing:
        flags.append({"id": "no_demo", "cn": "无 Demo", "severity": "medium", "evidence": []})

    fake = [pk["file"]["rel"] for pk in samples["pkgs"] if pk["format"] not in ("zip", "tar")]
    if fake:
        flags.append({"id": "fake_package", "cn": "伪 .skill 包（无法解压/缺 SKILL.md）",
                      "severity": "high", "evidence": fake})

    hollow = completeness["hollow"]
    if hollow:
        flags.append({"id": "hollow_file", "cn": "空壳文件（0 字节或仅占位符）",
                      "severity": "high", "evidence": hollow})

    if completeness["junk_files"]:
        flags.append({"id": "junk_files", "cn": "目录内含草稿/锁文件等垃圾",
                      "severity": "low", "evidence": completeness["junk_files"][:3]})

    return flags


def finalize_scores(r: dict, rubric: dict) -> None:
    """按当前各维度评级重算质量比率、红旗封顶、综合分与等级。

    eval_author 首次计算后调用；LLM 改判后也必须再次调用，
    否则「改判」只是装饰、不会体现在分数上。
    """
    vals = rubric["scoring"]["item_values"]
    quality_ratio = 0.0
    for c in r["criteria"].values():
        score = vals.get(c["rating"], c.get("score", 0.0))
        c["score"] = round(score, 3)
        quality_ratio += score * c["weight"]
    r["quality_ratio"] = round(quality_ratio, 4)

    comp = rubric["scoring"]["composite"]
    cw = comp["default_weights"]
    composite = (r["completeness"]["ratio"] * cw["completeness"]
                 + quality_ratio * cw["quality"]) * comp["scale"]

    cap = 100.0
    for fl in r["red_flags"]:
        spec = next((x for x in rubric["red_flags"] if x["id"] == fl["id"]), None)
        if spec:
            fl["hint"] = spec.get("hint", "")
            fl["cap_score"] = spec.get("cap_score", 100)
            cap = min(cap, spec["cap_score"])
    final = min(composite, cap)

    grade, grade_cn = "D", "需返工"
    for band in comp["grade_bands"]:
        if final >= band["min"]:
            grade, grade_cn = band["grade"], band["cn"]
            break

    r["composite_raw"] = round(composite, 1)
    r["cap"] = round(cap, 1)
    r["score"] = round(final, 1)
    r["grade"] = grade
    r["grade_cn"] = grade_cn


def eval_author(author: str, files: list[dict], content: dict, rubric: dict, profile: str) -> dict:
    completeness = check_completeness(files, content, rubric)
    samples = collect_samples(files, content, rubric)
    profile_cfg = rubric["quality_profiles"][profile]
    thresholds = rubric["scoring"]["rating_thresholds"]
    values = rubric["scoring"]["item_values"]

    criteria = OrderedDict()
    for cid, ccfg in profile_cfg["criteria"].items():
        items = []
        got = 0.0
        applicable = 0
        critical_failed = False
        for item in ccfg["items"]:
            res = eval_item(item, samples, files, rubric)
            items.append(res)
            if res["status"] == "na":
                continue
            applicable += 1
            if res["status"] == "pass":
                got += values["pass"]
            elif res["status"] == "partial":
                got += values["partial"]
            if res["critical"] and res["status"] != "pass":
                critical_failed = True
        score = (got / applicable) if applicable else 0.0
        # 评级规则：得分率达标 **且** 无关键项失守 → ✅；关键项失守时最高只能到 ⚠️
        if applicable == 0:
            rating = "na"
        elif score >= thresholds["pass"] and not critical_failed:
            rating = "pass"
        elif score >= thresholds["partial"]:
            rating = "partial"
        else:
            rating = "fail"
        criteria[cid] = {
            "label": ccfg["label"],
            "label_en": ccfg["label_en"],
            "intent": ccfg["intent"],
            "weight": ccfg["weight"],
            "score": round(score, 3),
            "rating": rating,
            "symbol": RATING_SYMBOL[rating],
            "critical_failed": critical_failed,
            "items": items,
            "failed_items": [i for i in items if i["status"] in ("fail", "partial")],
        }

    flags = detect_red_flags(files, samples, completeness, rubric)

    result = {
        "author": author,
        "profile": profile,
        "completeness": completeness,
        "criteria": criteria,
        "red_flags": flags,
        "file_count": len(files),
        "files": [f["rel"] for f in files],
        "convention_match": all(f.get("_convention_match", False) for f in files),
    }
    finalize_scores(result, rubric)
    return result


# --------------------------------------------------------------------------- #
# 5. LLM 混合层
# --------------------------------------------------------------------------- #

def emit_llm_prompt(results: list[dict], out_path: Path, profile: str) -> None:
    lines = [
        "# C4A 深审 Prompt（规则层 → LLM 层）",
        "",
        f"生成时间：{now_stamp()}　｜　评审档位：`{profile}`",
        "",
        "下面是规则层给出的**确定性初判与证据**。请你作为评审专家：",
        "1. 逐条复核规则判定是否合理（尤其 ⚠️/❌ 的项）；",
        "2. 指出规则可能误判的地方（例如把示例路径误判为硬编码）；",
        "3. 给出你对该作者各维度的最终评级。",
        "",
        "**输出格式（严格 JSON，不要多余文字）**：",
        "```json",
        '{"authors": {"<作者>": {"<维度id>": {"rating": "pass|partial|fail", "rationale": "一句话依据"}}}}',
        "```",
        "",
        "---",
        "",
    ]
    for r in results:
        lines.append(f"## 作者：{r['author']}（规则层：{r['score']}/100 · {r['grade']}）")
        lines.append("")
        lines.append(f"- 完整性：{r['completeness']['band']}（{r['completeness']['present']}/5，比率 {r['completeness']['ratio']}）")
        for cid, c in r["criteria"].items():
            lines.append(f"- **{c['label']}**（{cid}）规则判定：{c['symbol']} score={c['score']}")
            for it in c["items"]:
                ev = "；".join(it["evidence"]) if it["evidence"] else "—"
                lines.append(f"    - [{it['status']}] {it['check']} → {ev}")
        if r["red_flags"]:
            lines.append("- 红旗：" + "、".join(f["cn"] for f in r["red_flags"]))
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def apply_llm_verdicts(results: list[dict], verdicts: dict, rubric: dict) -> dict:
    """把 LLM 深审结论合并进规则层结果，并**重算分数**（改判必须体现在分数上）。

    返回一致率统计：一致率高说明规则层已足够；一致率低说明规则层存在系统性盲区。
    """
    stats = {"applied": 0, "agreed": 0, "compared": 0}
    authors = verdicts.get("authors", verdicts)
    for r in results:
        entry = authors.get(r["author"])
        if not entry:
            continue
        for cid, verdict in entry.items():
            if cid not in r["criteria"]:
                continue
            if isinstance(verdict, str):
                verdict = {"rating": verdict}
            rating = str(verdict.get("rating", "")).lower()
            if rating not in ("pass", "partial", "fail"):
                continue
            c = r["criteria"][cid]
            stats["compared"] += 1
            if rating == c["rating"]:
                stats["agreed"] += 1
            else:
                stats["applied"] += 1
                c["rule_rating"] = c["rating"]
                c["rule_score"] = c["score"]
                c["rating"] = rating
                c["symbol"] = RATING_SYMBOL[rating]
            c["source"] = "llm" if rating != c.get("rule_rating") else "rule"
            if verdict.get("rationale"):
                c["llm_rationale"] = verdict["rationale"]
        finalize_scores(r, rubric)
    stats["agreement"] = round(stats["agreed"] / stats["compared"], 3) if stats["compared"] else 1.0
    return stats


# --------------------------------------------------------------------------- #
# 6. Level 4 — 报告生成
# --------------------------------------------------------------------------- #

def class_overview(results: list[dict], rubric: dict) -> dict:
    n = len(results)
    if n == 0:
        return {"n": 0}
    complete = sum(1 for r in results if r["completeness"]["present"] == 5)
    partial = sum(1 for r in results if r["completeness"]["band"] == "部分缺失")
    insufficient = n - complete - partial
    avg_comp = sum(r["completeness"]["ratio"] for r in results) / n
    avg_qual = sum(r["quality_ratio"] for r in results) / n
    avg_score = sum(r["score"] for r in results) / n
    crit_ids = list(results[0]["criteria"].keys())
    dist = {}
    weakest = None
    for cid in crit_ids:
        counts = {"pass": 0, "partial": 0, "fail": 0, "na": 0}
        ssum = 0.0
        for r in results:
            counts[r["criteria"][cid]["rating"]] += 1
            ssum += r["criteria"][cid]["score"]
        dist[cid] = {"label": results[0]["criteria"][cid]["label"], "counts": counts,
                     "avg": round(ssum / n, 3)}
        if weakest is None or dist[cid]["avg"] < dist[weakest]["avg"]:
            weakest = cid
    missing_counter = defaultdict(int)
    for r in results:
        for k, v in r["completeness"]["slots"].items():
            if v["status"] != "✅":
                missing_counter[v["label"]] += 1
    most_missing = sorted(missing_counter.items(), key=lambda x: -x[1])[:2]
    return {
        "n": n, "complete": complete, "partial": partial, "insufficient": insufficient,
        "avg_completeness": round(avg_comp, 3), "avg_quality": round(avg_qual, 3),
        "avg_score": round(avg_score, 1), "distribution": dist, "weakest": weakest,
        "most_missing": most_missing,
        "flag_counter": {f["id"]: sum(1 for r in results if any(x["id"] == f["id"] for x in r["red_flags"]))
                         for f in rubric["red_flags"]},
    }


def build_suggestions(r: dict, rubric: dict) -> list[str]:
    out = []
    for k, v in r["completeness"]["slots"].items():
        if v["status"] == "❌":
            out.append(f"补交「{v['label']}」——当前完全缺失，直接触发「核心交付物缺失」红旗。")
        elif v["status"] == "⚠️":
            out.append(f"「{v['label']}」匹配较弱（{v['best'] or '无可信文件'}），建议按命名规范重命名或补全内容信号。")
    for cid, c in r["criteria"].items():
        for it in c["failed_items"][:2]:
            if it["fix"]:
                out.append(f"【{c['label']}】{it['fix']}")
    for fl in r["red_flags"]:
        if fl["severity"] in ("critical", "high") and fl.get("hint"):
            out.append(f"⚠️ 红旗「{fl['cn']}」：{fl['hint']}")
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            uniq.append(s)
            seen.add(s)
    return uniq[:6]


def render_markdown(results: list[dict], overview: dict, meta: dict, rubric: dict, llm_stats: dict | None,
                    samples_note: str = "") -> str:
    L = []
    A = L.append
    A(f"# C4 提交自动评审报告")
    A("")
    A(f"> 生成时间：{meta['timestamp']}　｜　评审档位：`{meta['profile']}`　｜　扫描路径：`{meta['input']}`")
    A(f"> 识别提交：**{overview['n']}** 位作者 / {meta['file_count']} 个文件　｜　评审器：`c4-skill-evaluator` v1.0.0")
    A("")
    if samples_note.strip():
        A(samples_note.strip())
        A("")
    A("---")
    A("")
    A("## 一、班级总览")
    A("")
    A("| 指标 | 数值 |")
    A("|------|------|")
    A(f"| 提交人数 | {overview['n']} |")
    A(f"| 完整提交（5/5） | {overview['complete']} |")
    A(f"| 部分缺失 | {overview['partial']} |")
    A(f"| 严重缺失（<3 类） | {overview['insufficient']} |")
    A(f"| 平均完整性 | {overview['avg_completeness'] * 100:.1f}% |")
    A(f"| 平均质量分 | {overview['avg_quality'] * 100:.1f} / 100 |")
    A(f"| 平均综合分 | {overview['avg_score']} / 100 |")
    A("")
    A("### 质量分布（各维度 ✅/⚠️/❌ 人数）")
    A("")
    A("| 维度 | ✅ | ⚠️ | ❌ | 平均得分率 |")
    A("|------|---|---|---|-----------|")
    for cid, d in overview["distribution"].items():
        c = d["counts"]
        A(f"| {d['label']} | {c['pass']} | {c['partial']} | {c['fail']} | {d['avg'] * 100:.0f}% |")
    A("")

    A("## 二、排名")
    A("")
    A("| 排名 | 作者 | 完整性 | 质量分 | 综合分 | 等级 | 红旗 |")
    A("|------|------|--------|--------|--------|------|------|")
    for i, r in enumerate(results, 1):
        flags = "、".join(f["cn"] for f in r["red_flags"]) or "—"
        A(f"| {i} | {r['author']} | {r['completeness']['band_symbol']} {r['completeness']['present']}/5 | "
          f"{r['quality_ratio'] * 100:.1f} | **{r['score']}** | {r['grade']}（{r['grade_cn']}） | {flags} |")
    A("")

    if llm_stats:
        A("### 规则层 vs LLM 层一致率")
        A("")
        A(f"- 参与比对维度：{llm_stats['compared']}　｜　一致：{llm_stats['agreed']}　｜　"
          f"LLM 改判：{llm_stats['applied']}　｜　一致率 **{llm_stats['agreement'] * 100:.1f}%**")
        A("")

    A("## 三、作者详情")
    A("")
    for r in results:
        A(f"### {r['author']}　—　{r['score']}/100　{r['grade']}（{r['grade_cn']}）")
        A("")
        A(f"- 文件数：{r['file_count']}　｜　命名规范：{'✅ 符合' if r['convention_match'] else '⚠️ 部分文件未按 `姓名_挑战_内容.扩展名` 规范'}")
        A(f"- 综合分：完整性 {r['completeness']['ratio'] * 100:.0f}% × 0.4 ＋ 质量 {r['quality_ratio'] * 100:.0f}% × 0.6 = "
          f"{r['composite_raw']}，红旗封顶后 **{r['score']}**")
        A("")
        A("**完整性检查（5 类必须交付物）**")
        A("")
        A("| 交付物 | 状态 | 权值 | 命中文件 | 证据 |")
        A("|--------|------|------|----------|------|")
        for k, v in r["completeness"]["slots"].items():
            ev = "；".join(v["evidence"][:2]) or "—"
            A(f"| {v['label']} | {v['status']} | {v['weight']:.2f} | {v['best'] or '—'} | {ev} |")
        A("")
        if r["completeness"]["extra_files"]:
            A(f"附加文件（不计分）：{'、'.join(r['completeness']['extra_files'][:6])}")
            A("")
        A("**质量评审**")
        A("")
        A("| 条件 | 评级 | 得分 | 检查项通过情况 |")
        A("|------|------|------|----------------|")
        for cid, c in r["criteria"].items():
            ok = sum(1 for i in c["items"] if i["status"] == "pass")
            na = sum(1 for i in c["items"] if i["status"] == "na")
            ap = len(c["items"]) - na
            src = "（LLM）" if c.get("source") == "llm" else ""
            A(f"| {c['label']}{src} | {c['symbol']} | {c['score'] * 100:.0f}% | {ok}/{ap} |")
        A("")
        A("<details><summary>检查项明细与证据</summary>")
        A("")
        for cid, c in r["criteria"].items():
            A(f"- **{c['label']}**（{c['intent']}）")
            for it in c["items"]:
                ev = "；".join(it["evidence"]) or "—"
                A(f"    - `{it['status']}` {it['check']} → {ev}")
            if c.get("llm_rationale"):
                A(f"    - LLM 改判依据：{c['llm_rationale']}")
        A("")
        A("</details>")
        A("")
        if r["red_flags"]:
            A("**红旗**")
            A("")
            for fl in r["red_flags"]:
                ev = ("；".join(fl["evidence"])) if fl["evidence"] else ""
                A(f"- 🔴 **{fl['cn']}**（{fl['severity']}，封顶 {fl.get('cap_score', '—')}）{ev}")
            A("")
        sug = build_suggestions(r, rubric)
        A("**改进建议**")
        A("")
        for i, s in enumerate(sug, 1):
            A(f"{i}. {s}")
        A("")
        A("---")
        A("")

    A("## 四、全班改进建议")
    A("")
    if overview["most_missing"]:
        items = "、".join(f"{k}（{v} 人）" for k, v in overview["most_missing"])
        A(f"- **最常见缺失**：{items}")
    if overview["weakest"]:
        w = overview["distribution"][overview["weakest"]]
        A(f"- **最弱维度**：{w['label']}（平均得分率 {w['avg'] * 100:.0f}%）")
    A(f"- **提交前自检命令**：`python scripts/c4a_evaluate.py --input <你的提交文件夹>`")
    A("- 建议流程：先跑评审器 → 按红旗清单返工 → 重跑至「无 high/critical 红旗」再提交。")
    A("")
    A("## 五、方法说明")
    A("")
    A("本报告由 `c4-skill-evaluator` 自动生成，评审逻辑完全由 "
      "`references/c4a_rubric.json` 配置驱动：")
    A("")
    A("- **完整性**：5 类交付物加权（可执行 0.30 / Skill说明 0.25 / Demo 0.15 / 教学 0.15 / AI日志 0.15），"
      "采用「文件×交付物」打分后贪心唯一分配，避免一个文件多处分摊。")
    A("- **质量**：每维度拆成 4–5 条可判定检查项，逐项给 ✅/⚠️/❌/—（不适用项不计入分母），"
      "维度得分率 ≥0.75 → ✅，≥0.40 → ⚠️，否则 ❌。")
    A("- **反套壳**：`.skill` 是否真能解压、`SKILL.md` 是否真有 frontmatter、Python 是否真能 `compile()`、"
      "文档声称的脚本是否真存在——全部实测，不信关键词。")
    A("- **红旗封顶**：安全类问题（密钥泄露）封顶 40 分，缺交付物封顶 50 分，空壳文件封顶 60 分。")
    A("")
    return "\n".join(L)


def write_csv(results: list[dict], out_path: Path, profile: str) -> None:
    with open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        crit_ids = list(results[0]["criteria"].keys()) if results else []
        head = ["作者", "文件数", "完整性(命中/5)", "完整性比率"] + \
               [f"{results[0]['criteria'][c]['label']}({c})" for c in crit_ids] + \
               ["质量比率", "综合分(封顶前)", "封顶", "最终分", "等级", "红旗", "主要缺口"]
        w.writerow(head)
        for r in results:
            missing = [v["label"] for v in r["completeness"]["slots"].values() if v["status"] != "✅"]
            row = [r["author"], r["file_count"], r["completeness"]["present"], r["completeness"]["ratio"]] + \
                  [f"{r['criteria'][c]['symbol']}{r['criteria'][c]['score']}" for c in crit_ids] + \
                  [r["quality_ratio"], r["composite_raw"], r["cap"], r["score"], r["grade"],
                   "；".join(f["cn"] for f in r["red_flags"]), "；".join(missing)]
            w.writerow(row)


def write_csv_items(results: list[dict], out_path: Path) -> None:
    with open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["作者", "维度", "检查项", "判定", "证据", "改进提示"])
        for r in results:
            for cid, c in r["criteria"].items():
                for it in c["items"]:
                    w.writerow([r["author"], c["label"], it["check"], it["status"],
                                "；".join(it["evidence"]), it["fix"]])


def render_html(results: list[dict], overview: dict, meta: dict, profile: str) -> str:
    def esc(x):
        return html.escape(str(x))

    css = """
    :root{--bg:#f7f8fa;--card:#ffffff;--ink:#1c1f23;--sub:#5b6470;--line:#e4e8ee;
      --green:#12805c;--amber:#b06f00;--red:#c0392b;--blue:#2f5496;--chip:#eef2f7}
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:var(--ink);
      font:15px/1.65 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}
    .wrap{max-width:1080px;margin:0 auto;padding:32px 20px 64px}
    h1{font-size:26px;margin:0 0 6px}
    h2{font-size:19px;margin:34px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--line)}
    .meta{color:var(--sub);font-size:13px;margin-bottom:22px}
    .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
    .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
    .card .k{font-size:12px;color:var(--sub)}
    .card .v{font-size:24px;font-weight:600;margin-top:4px}
    table{width:100%;border-collapse:collapse;background:var(--card);
      border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:14px}
    th,td{padding:9px 11px;text-align:left;border-bottom:1px solid var(--line)}
    th{background:var(--chip);font-weight:600;font-size:13px}
    tr:last-child td{border-bottom:none}
    .bar{height:9px;background:var(--chip);border-radius:5px;overflow:hidden;min-width:78px}
    .bar>i{display:block;height:100%;background:var(--blue)}
    .author{background:var(--card);border:1px solid var(--line);border-radius:12px;
      padding:18px 20px;margin:14px 0}
    .author h3{margin:0 0 4px;font-size:17px}
    .author .sub{color:var(--sub);font-size:13px;margin-bottom:12px}
    .chips span{display:inline-block;background:var(--chip);border-radius:20px;
      padding:2px 10px;margin:0 6px 6px 0;font-size:12px;color:var(--sub)}
    .flag{border-left:4px solid var(--red);background:#fdf3f2;padding:8px 12px;
      border-radius:6px;margin:6px 0;font-size:13px}
    .flag.medium{border-color:var(--amber);background:#fdf8ee}
    .flag.low{border-color:var(--sub);background:#f4f6f8}
    ul.sug{margin:8px 0 0 18px;padding:0}
    ul.sug li{margin:3px 0}
    .ok{color:var(--green)}.warn{color:var(--amber)}.bad{color:var(--red)}
    .note{color:var(--sub);font-size:13px}
    """
    H = [f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>",
         f"<title>C4 提交自动评审报告</title><style>{css}</style></head><body><div class='wrap'>"]
    H.append("<h1>C4 提交自动评审报告</h1>")
    H.append(f"<div class='meta'>生成时间 {esc(meta['timestamp'])} ｜ 档位 <code>{esc(profile)}</code> "
             f"｜ 扫描路径 <code>{esc(meta['input'])}</code> ｜ 评审器 c4-skill-evaluator v1.0.0</div>")

    H.append("<div class='cards'>")
    for k, v in [("提交人数", overview["n"]), ("完整 5/5", overview["complete"]),
                 ("平均完整性", f"{overview['avg_completeness'] * 100:.0f}%"),
                 ("平均质量", f"{overview['avg_quality'] * 100:.0f}"),
                 ("平均综合分", overview["avg_score"])]:
        H.append(f"<div class='card'><div class='k'>{esc(k)}</div><div class='v'>{esc(v)}</div></div>")
    H.append("</div>")

    H.append("<h2>质量分布</h2><table><tr><th>维度</th><th>✅</th><th>⚠️</th><th>❌</th><th>平均得分率</th></tr>")
    for cid, d in overview["distribution"].items():
        c = d["counts"]
        H.append(f"<tr><td>{esc(d['label'])}</td><td class='ok'>{c['pass']}</td>"
                 f"<td class='warn'>{c['partial']}</td><td class='bad'>{c['fail']}</td>"
                 f"<td><div class='bar'><i style='width:{d['avg'] * 100:.0f}%'></i></div>"
                 f"<span class='note'>{d['avg'] * 100:.0f}%</span></td></tr>")
    H.append("</table>")

    H.append("<h2>排名</h2><table><tr><th>#</th><th>作者</th><th>完整性</th><th>质量</th>"
             "<th>综合分</th><th>等级</th><th>红旗</th></tr>")
    for i, r in enumerate(results, 1):
        cls = "ok" if r["grade"] == "A" else ("warn" if r["grade"] in ("B", "C") else "bad")
        flags = "、".join(f["cn"] for f in r["red_flags"]) or "—"
        H.append(f"<tr><td>{i}</td><td><b>{esc(r['author'])}</b></td>"
                 f"<td>{r['completeness']['band_symbol']} {r['completeness']['present']}/5</td>"
                 f"<td><div class='bar'><i style='width:{r['quality_ratio'] * 100:.0f}%'></i></div>"
                 f"<span class='note'>{r['quality_ratio'] * 100:.0f}</span></td>"
                 f"<td class='{cls}'><b>{r['score']}</b></td><td class='{cls}'>{esc(r['grade'])} {esc(r['grade_cn'])}</td>"
                 f"<td class='note'>{esc(flags)}</td></tr>")
    H.append("</table>")

    H.append("<h2>作者详情</h2>")
    for r in results:
        H.append("<div class='author'>")
        H.append(f"<h3>{esc(r['author'])} — {r['score']}/100 {esc(r['grade'])}（{esc(r['grade_cn'])}）</h3>")
        H.append(f"<div class='sub'>文件 {r['file_count']} 个 ｜ 完整性 {r['completeness']['band']} "
                 f"（{r['completeness']['present']}/5）｜ 质量得分率 {r['quality_ratio'] * 100:.0f}%</div>")
        H.append("<table><tr><th>条件</th><th>评级</th><th>得分率</th><th>依据</th></tr>")
        for cid, c in r["criteria"].items():
            src = "（LLM）" if c.get("source") == "llm" else ""
            ok = sum(1 for i in c["items"] if i["status"] == "pass")
            ap = sum(1 for i in c["items"] if i["status"] != "na")
            brief = "；".join(i["evidence"][0] for i in c["items"] if i["status"] == "pass" and i["evidence"])[:110] or "—"
            H.append(f"<tr><td>{esc(c['label'])}{src}</td><td>{c['symbol']}</td>"
                     f"<td><div class='bar'><i style='width:{c['score'] * 100:.0f}%'></i></div>"
                     f"<span class='note'>{ok}/{ap}</span></td><td class='note'>{esc(brief)}</td></tr>")
        H.append("</table>")
        slack = [v["label"] for v in r["completeness"]["slots"].values() if v["status"] != "✅"]
        if slack:
            H.append("<div class='chips'>缺失/弱匹配：" + "".join(f"<span>{esc(x)}</span>" for x in slack) + "</div>")
        for fl in r["red_flags"]:
            ev = "；".join(fl["evidence"]) if fl["evidence"] else ""
            H.append(f"<div class='flag {esc(fl['severity'])}'><b>{esc(fl['cn'])}</b>"
                     f"（{esc(fl['severity'])}）{esc(ev)}</div>")
        sugs = build_suggestions(r, {})
        if sugs:
            H.append("<ul class='sug'>" + "".join(f"<li>{esc(s)}</li>" for s in sugs) + "</ul>")
        H.append("</div>")

    H.append("<h2>全班改进建议</h2><ul class='sug'>")
    if overview["most_missing"]:
        H.append("<li>最常见缺失：" + esc("、".join(f"{k}（{v} 人）" for k, v in overview["most_missing"])) + "</li>")
    if overview["weakest"]:
        w = overview["distribution"][overview["weakest"]]
        H.append(f"<li>最弱维度：{esc(w['label'])}（平均得分率 {w['avg'] * 100:.0f}%）</li>")
    H.append("<li>提交前自检：<code>python scripts/c4a_evaluate.py --input &lt;提交文件夹&gt;</code></li>")
    H.append("</ul></div></body></html>")
    return "".join(H)


# --------------------------------------------------------------------------- #
# 7. 主流程
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description="C4A 技能提交自动评审器")
    ap.add_argument("--input", "-i", required=True, help="包含 C4 提交的本地文件夹路径")
    ap.add_argument("--outdir", "-o", default=None, help="报告输出目录（默认 <input>/_c4a_review）")
    ap.add_argument("--rubric", default=str(DEFAULT_RUBRIC), help="评分配置 JSON 路径")
    ap.add_argument("--profile", default="c4_four_conditions",
                    choices=["c4_four_conditions", "platform_100"], help="评审档位")
    ap.add_argument("--challenge", default=None, help="只评审该挑战标识的提交（如 C4 / C4A）")
    ap.add_argument("--exclude", action="append", default=[], help="排除目录（可重复）")
    ap.add_argument("--prefix", default="lishengdan_C4A", help="报告文件名前缀")
    ap.add_argument("--samples-note", default=None, help="样本来源说明 Markdown 文件，注入报告开头（可追溯数据出处）")
    ap.add_argument("--emit-llm-prompt", action="store_true", help="导出 LLM 深审 prompt")
    ap.add_argument("--llm-verdicts", default=None, help="回灌 LLM 结论 JSON")
    ap.add_argument("--quiet-json", action="store_true", help="只输出 JSON 到 stdout")
    args = ap.parse_args()

    root = Path(args.input).expanduser().resolve()
    if not root.is_dir():
        log(f"ERROR: 输入路径不是目录：{root}")
        return 1
    rubric = load_rubric(Path(args.rubric).expanduser().resolve())
    excludes = [Path(e).expanduser().resolve() for e in args.exclude]

    files = scan_folder(root, rubric, excludes)
    log(f"[1/4] 扫描完成：{len(files)} 个文件")

    content = build_content_index(files, rubric)

    buckets: dict[str, list[dict]] = defaultdict(list)
    version_index: dict[str, set] = defaultdict(set)
    unconv = 0
    for fi in files:
        info = resolve_author(fi, root, content["text"], rubric)
        author = info["author"]
        base, ver = split_version(fi["stem"], author, rubric)
        fi["_author"] = author
        fi["_base"] = base
        fi["_version"] = ver
        fi["_challenge_hint"] = info["challenge"]
        fi["_convention_match"] = info["convention_match"]
        if not info["convention_match"]:
            unconv += 1
        if args.challenge and info["challenge"] and info["challenge"].upper() != args.challenge.upper():
            continue
        buckets[author].append(fi)
        if ver:
            version_index[base].add(ver)

    log(f"[2/4] 作者识别：{len(buckets)} 位（不规范命名 {unconv} 个文件）")

    results = []
    for author, afiles in sorted(buckets.items()):
        r = eval_author(author, afiles, content, rubric, args.profile)
        results.append(r)
    results.sort(key=lambda r: (-r["score"], r["author"]))

    llm_stats = None
    if args.llm_verdicts:
        verdicts = json.loads(Path(args.llm_verdicts).read_text(encoding="utf-8"))
        llm_stats = apply_llm_verdicts(results, verdicts, rubric)
        results.sort(key=lambda r: (-r["score"], r["author"]))

    overview = class_overview(results, rubric)

    # 版本追踪
    timeline = []
    for base, vers in sorted(version_index.items()):
        if len(vers) < 2:
            continue
        seq = []
        for v in sorted(vers):
            hit = next((r for r in results if r["author"] == f"{base}_v{v}"), None)
            if hit:
                seq.append({"version": f"v{v}", "score": hit["score"], "grade": hit["grade"]})
        if len(seq) >= 2:
            delta = seq[-1]["score"] - seq[0]["score"]
            timeline.append({"base": base, "seq": seq, "delta": round(delta, 1),
                             "trend": "↑ 进步" if delta > 0 else ("↓ 退步" if delta < 0 else "→ 持平")})

    outdir = Path(args.outdir).expanduser().resolve() if args.outdir else root / "_c4a_review"
    outdir.mkdir(parents=True, exist_ok=True)

    meta = {"timestamp": now_stamp(), "input": str(root), "profile": args.profile,
            "file_count": len(files), "author_count": len(results)}

    md_path = outdir / f"{args.prefix}_评审报告.md"
    csv_path = outdir / f"{args.prefix}_评审明细.csv"
    csv_items = outdir / f"{args.prefix}_评审明细_检查项.csv"
    html_path = outdir / f"{args.prefix}_评审报告.html"
    json_path = outdir / "evaluation_result.json"

    md = render_markdown(results, overview, meta, rubric, llm_stats,
                         Path(args.samples_note).read_text(encoding="utf-8") if args.samples_note else "")
    if timeline:
        md += "\n## 六、版本追踪（迭代轨迹）\n\n"
        md += "| 作者 | 轨迹 | 变化 |\n|------|------|------|\n"
        for t in timeline:
            traj = " → ".join(f"{s['version']} {s['score']}" for s in t["seq"])
            md += f"| {t['base']} | {traj} | {t['trend']}（{t['delta']:+}） |\n"
        md += "\n"
    md_path.write_text(md, encoding="utf-8")
    write_csv(results, csv_path, args.profile)
    write_csv_items(results, csv_items)
    html_path.write_text(render_html(results, overview, meta, args.profile), encoding="utf-8")

    payload = {"meta": meta, "overview": overview, "llm_stats": llm_stats,
               "timeline": timeline, "results": results}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.emit_llm_prompt:
        emit_llm_prompt(results, outdir / "llm_prompt.md", args.profile)

    log(f"[3/4] 报告已生成：{md_path.name} / {csv_path.name} / {html_path.name} / {json_path.name}")

    critical = sum(1 for r in results for f in r["red_flags"] if f["severity"] in ("critical", "high"))
    log(f"[4/4] 高严重度红旗：{critical} 项")

    if args.quiet_json:
        print(json.dumps({"meta": meta, "overview": overview,
                          "results": [{"author": r["author"], "score": r["score"], "grade": r["grade"],
                                       "completeness": r["completeness"]["present"],
                                       "flags": [f["id"] for f in r["red_flags"]]} for r in results]},
                         ensure_ascii=False))
    else:
        print(f"\n{'=' * 62}")
        print(f"C4 提交自动评审 · 档位 {args.profile} · {meta['timestamp']}")
        print(f"{'=' * 62}")
        print(f"{'作者':<22}{'完整':<8}{'质量':<8}{'综合分':<9}{'等级':<6}红旗")
        print("-" * 62)
        for r in results:
            flags = "、".join(f["cn"] for f in r["red_flags"]) or "—"
            print(f"{r['author']:<22}{r['completeness']['present']}/5     "
                  f"{r['quality_ratio'] * 100:>5.0f}   {r['score']:>6.1f}   "
                  f"{r['grade']:<5} {flags}")
        print("-" * 62)
        print(f"平均综合分 {overview['avg_score']}/100　｜　报告：{md_path}")
        print(f"{'=' * 62}\n")

    return 2 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
