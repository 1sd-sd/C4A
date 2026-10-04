---
name: c4-skill-evaluator
description: >
  Automated evaluator for Elite20 C4 skill submissions. Point it at a local folder
  (a WeChat group export, a manual download folder, or any directory of submissions)
  and it identifies each author, checks the five required deliverables, grades quality
  against the C4 four criteria (Reusable / Executable / Verifiable / Clear I/O) with
  per-item evidence, raises red flags (missing artifacts, hollow files, fake .skill
  packages, leaked secrets, draft junk), ranks the class, and writes Markdown + CSV +
  HTML reports. Optional LLM deep-review layer (--emit-llm-prompt / --llm-verdicts)
  catches semantic problems rules cannot see, e.g. code that contradicts reality.
  Use when the user says "evaluate C4 submissions", "review skill submissions",
  "check submission completeness", "评审C4提交", "自动评审技能", "技能提交检查",
  "C4评审报告", "class submission dashboard", or gives a folder of skill submissions
  and asks who submitted what / who is missing what / how good it is.
  Also trigger when someone asks to grade, rank, or audit a batch of .skill packages.
---

# C4 Skill Submission Evaluator

## Purpose

C4 asks every student to hand in a reusable skill package. The hard part is not
collecting the files — it is judging them consistently. This skill turns a shared
folder into a graded, evidence-backed review in one command.

It is a **rubric-driven, hybrid evaluator**:

```
folder ──► ① scan & group by author
            ② completeness check (5 required deliverables, weighted + greedy unique assignment)
            ③ quality review (4 criteria × 4–5 deterministic check items each)
            ④ reports (Markdown + CSV + HTML) + red flags + ranking + version tracking
                     └─► optional LLM deep-review round (rule verdicts → LLM verdicts → recompute)
```

Analogy: a teaching assistant who sorts the pile by student, ticks the checklist,
grades against a published rubric, writes the feedback, and still escalates the
genuinely ambiguous cases to a human (or an LLM).

## Input / Output

| Direction | Content |
|-----------|---------|
| **Input** | A local folder path containing submissions. Optional: rubric JSON, profile, LLM verdicts JSON. |
| **Output** | `*_评审报告.md`, `*_评审明细.csv`, `*_评审明细_检查项.csv`, `*_评审报告.html`, `evaluation_result.json` |

**IO one-liner**: 输入一个装着提交的本地文件夹路径，输出「谁交了什么 / 齐不齐 / 好不好 / 下一步改什么」。

## Workflow

### Step 1 — Scan and identify authors

```bash
python scripts/c4a_evaluate.py --input "<提交文件夹>" --outdir "<输出目录>"
```

Author extraction chain (first hit wins, source recorded):

1. Filename convention `作者_挑战_内容.扩展名` (regex from `references/c4a_rubric.json`)
2. Top-level folder name (files grouped per author)
3. Document header (`姓名：` / `Author:`)
4. DOCX metadata (`docProps/core.xml`)
5. `Unknown` — flagged for manual review

Iteration versions (`_v1` / `_v2`) are separated out for version tracking.

### Step 2 — Completeness check

Five required deliverables, weighted: **可执行 0.30 / Skill说明 0.25 / Demo 0.15 / 教学说明 0.15 / AI日志 0.15**.

Every `file × deliverable` pair is scored (filename signals, extension, content signals),
then assigned **greedily by descending score so one file can only fill one slot** —
this stops a single README from being counted as three deliverables.

`accept_ext` is a **hard filter**: a `rubric.yaml` that happens to contain the literal
words 输入/输出 can never be mistaken for a "Skill 说明文档".

### Step 3 — Quality review (four criteria)

Each criterion is decomposed into 4–5 deterministic check items. Each item returns
`pass / partial / fail / na` plus concrete evidence. **`na` items are excluded from the
denominator**, so a submission is never punished for checks that do not apply.

Rating: `score ≥ 0.80 → ✅`, `≥ 0.40 → ⚠️`, else `❌` — **and a failed *critical* item caps
the criterion at ⚠️** (hardcoded absolute paths in code; broken/fake `.skill` package;
missing `SKILL.md` frontmatter; empty demo; missing "输入X，输出Y" one-liner).

Anti-gaming is explicit — claims are verified, never trusted:

| Claim | How it is actually verified |
|-------|-----------------------------|
| "Here is my `.skill`" | unzip it; must be zip/tar **and** contain `SKILL.md` |
| "It has a SKILL.md" | parse the frontmatter; `name` present, `description` ≥ 20 chars |
| "The code runs" | `compile()` every `.py` — including files **inside** the package |
| "Paths are portable" | regex the code for `C:\`, `/Users/`, `/home/`, `/mnt/`, UNC |

### Step 4 — Reports and red flags

- Class dashboard, quality distribution, ranking (configurable weights, default 0.4 completeness + 0.6 quality)
- Red flags with score caps: `secret_leak` → 40, `missing_artifacts` → 50, `fake_package` → 55, `hollow_file` → 60
- Per-author improvement suggestions generated from the failed items' `fix` hints
- Version tracking for `_v2` / `_v3` with a trajectory table
- Exit code **2** when any critical/high red flag exists → usable as a CI gate

### Step 5 (optional) — LLM deep review

```bash
# 1) export the rule verdicts as a review prompt
python scripts/c4a_evaluate.py --input "<folder>" --outdir out --emit-llm-prompt
# 2) let an LLM answer in the strict JSON contract
# 3) merge back: scores are RECOMPUTED, and the rule-vs-LLM agreement rate is reported
python scripts/c4a_evaluate.py --input "<folder>" --outdir out2 --llm-verdicts verdicts.json
```

Use it for what rules provably cannot do — for example, a skill whose `SKILL.md` says
`tarfile.open(path, "r:gz")` while real `.skill` files are zip archives. The rule layer
sees a valid package; only a reader sees that the code contradicts reality.

## Edge cases

| Situation | Handling |
|-----------|----------|
| Empty folder | Reports "no submissions found" and exits cleanly |
| Non-standard filenames | Falls back to folder/header/metadata; marks naming as non-conforming |
| File < 32 bytes | Treated as a hollow shell; the slot is marked ⚠️ and counts as missing |
| `.skill` that is not an archive | `fake_package` red flag, capped score |
| Fake secrets in test fixtures | Excluded via the fixture-path/context guard, recorded as an info note (not a leak) |
| Oversized files (>256 KB text / >50 MB binary) | Name and type matching only, content skipped |
| Mixed-in non-submission files | Listed separately as "additional files", excluded from scoring |

## References

- `references/c4a_rubric.json` — **all** signals, weights, thresholds and red-flag caps. Edit here, not in code.
- `references/scoring_guide.md` — the published scoring rules, so anyone can recompute a score by hand.
- `examples/run_selftest.py` — assertion-based self-test on a labelled synthetic corpus; prints accuracy and false-positive rate.
- `examples/make_synthetic_corpus.py` — regenerates the labelled corpus deterministically (zero-dependency PNG writer included).
- `examples/real_corpus/` — four real, non-synthetic artifacts used as hold-out regression checks.

## Principles

- **Published, not opaque.** Every score traces to a named check item and to evidence text.
- **Deterministic.** Same input → byte-identical output. Verified by the self-test.
- **Honest about limits.** The self-test prints its own blind spots instead of hiding them.
