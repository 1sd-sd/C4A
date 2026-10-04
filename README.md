# C4A 提交成果 · 技能提交自动评审器

> **挑战**：C4A 技能提交自动评审（Automated Skill Submission Evaluator）｜ challenge_id `ch-20260717031432-5jvqje`
> **作者**：lishengdan ｜ **完成级别**：Level 1–4 全部 ｜ **日期**：2026-10-04
>
> 仓库：<https://github.com/1sd-sd/C4A>（Public，main 分支）

---

## 这是什么

**`c4-skill-evaluator`** —— 一个把"C4 提交文件夹"变成"带证据的评审报告"的技能。

```
输入：一个装着 C4 提交的本地文件夹路径
输出：谁交了什么 / 齐不齐 / 好不好 / 下一步改什么（Markdown + CSV + HTML + JSON）
```

**零第三方依赖**（Python 3.9+，不联网，不改动被评审目录）。

## 30 秒跑起来

```bash
# 0. 拿到成果
git clone https://github.com/1sd-sd/C4A.git && cd C4A

# 一键复现全部产物（报告 / 自测 / demo / 技能包 / 脱敏自检）；无 pillow 时加 --no-demo
python lishengdan_C4A_复现脚本.py

# 只想跑评审器本体（输入一个装着 C4 提交的文件夹）
python src/c4-skill-evaluator/scripts/c4a_evaluate.py \
    --input src/c4-skill-evaluator/examples/real_corpus --outdir /tmp/review

# 验证技能本身没坏（43 项自测，预期准确率 100%）
python src/c4-skill-evaluator/examples/run_selftest.py
```

## 核心数字（全部可复跑）

| 指标 | 数值 | 证据 |
|------|------|------|
| 自测准确率 | **43/43 = 100.0%**（初始版本 68.8%，校准过程已披露） | `lishengdan_C4A_评测器自测报告.md` |
| 误判率 | **0.0%** | 同上 |
| 确定性 | 同一输入两次运行**逐字节一致** | 自测第 4 条回归断言 |
| 真实语料回归断言 | 4/4 通过 | 同上 |
| 规则 vs LLM 一致率 | **81.2%**（16 维度：一致 13，改判 3） | `lishengdan_C4A_评审报告_深审版.md` |
| 反套壳对照 | 空壳提交 29/D，真实齐全提交 100/A（同一评审器） | `demo/lishengdan_C4A_demo_3_反套壳对照.png` |
| 交叉自检（C4 的 checker） | 全量 **80.3 FAIL**（含刻意坏样本）/ 排除测试语料 **99.2 PASS** | `评审产物/交叉自检_C4技能*/` |

## 交付物清单

| 文件 | 对应挑战要求 | 说明 |
|------|--------------|------|
| `lishengdan_C4A_方案设计.md` | 方案设计文档 | 架构、评审维度定义、技术选型理由、六项核心决策的取舍 |
| `lishengdan_C4A_skill-evaluator.skill` | 可安装技能包 | zip，含源码 / 配置 / 两套语料 / 自测套件 |
| `lishengdan_C4A_评审报告.md` | 真实评审报告 | 规则层输出，**确定性、可逐字节复现** |
| `lishengdan_C4A_评审报告_深审版.md` | （加分）规则+LLM 混合 | 含一致率与 3 处改判的实证依据 |
| `lishengdan_C4A_教学说明.md` | 教学说明 | 怎么装、怎么用、输入什么得到什么、常见坑 |
| `lishengdan_C4A_AI日志.md` | AI 日志 | 9 轮迭代，6 轮是 AI 自己修自己的 bug |
| `lishengdan_C4A_拿来说明.md` | 拿来说明 | 从 wechat-doc-mapper 拿了什么 / 改了什么 / 为什么 |
| `lishengdan_C4A_复盘AAR.md` | 复盘 | 四次"差点被骗"的洞察 + 6 条可验证的改进方案 |
| `lishengdan_C4A_复现脚本.py` | （可复现性） | 一条命令重建报告 / 自测 / demo / 技能包，并做脱敏自检 |
| `lishengdan_C4A_评测器自测报告.md` | （评审器质量证据） | 准确率 / 误判率 / 已知局限 |
| `lishengdan_C4A_评审明细.csv` `_检查项.csv` | （Excel 详表的零依赖替代） | 作者级 + 检查项级 |
| `lishengdan_C4A_评审报告.html` | （Level 4 可视化） | 班级仪表板，离线可开 |
| `demo/*.png` | Demo | 6 张真实运行截图（生成脚本可复跑） |

## 目录结构

```
C4A提交成果/
├── lishengdan_C4A_*.md / *.csv / *.html / *.skill   ← 提交文件（命名规范）
├── lishengdan_C4A_复现脚本.py                        ← 一键重建全部产物
├── src/c4-skill-evaluator/                          ← 技能源码（与 .skill 包内一致）
│   ├── SKILL.md                        技能主指令
│   ├── scripts/c4a_evaluate.py         评测器（1519 行，零依赖）
│   ├── references/c4a_rubric.json      评分配置（所有信号/权重/阈值/封顶）
│   ├── references/scoring_guide.md     评分说明书（可手算复核）
│   └── examples/
│       ├── make_synthetic_corpus.py    合成评测集生成器（确定性）
│       ├── ground_truth.json           标准答案（含校准日志）
│       ├── run_selftest.py             自测套件（准确率/误判率/确定性）
│       ├── synthetic_corpus/           7 份带标注合成样本（含刻意坏样本）
│       └── real_corpus/                4 份真实材料（hold-out 回归）
├── 评审产物/                                        ← llm_prompt / llm_verdicts / evaluation_result / 交叉自检
├── demo/                                            ← 6 张真实运行截图 + 生成脚本
└── 参考资料/                                        ← 挑战原始材料
```

> ⚠️ `examples/synthetic_corpus/` 里**故意**放了 4 份坏样本（空壳、假 zip、缺 frontmatter）。
> 任何"逐文件判定、无夹具概念"的全量扫描器都会命中它们 —— 这正是本技能要解决的问题。
> 交叉自检的完整证据（含 FAIL 与对照 PASS 两跑）见 `评审产物/交叉自检_C4技能*/`。

## 设计要点（三句话版）

1. **配置驱动**：评审逻辑全在 `c4a_rubric.json`，改权重/阈值/信号词不动代码。
2. **实测而非轻信**：`.skill` 真解包、frontmatter 真解析、Python 真 `compile()`（含包内）、路径真扫描；命中文件 <32 B 判空壳。
3. **规则 + LLM 混合且改判会重算分数**：一致率 81.2% 本身就是"规则层盲区地图"。

## 已知局限（不藏着）

- 自测集 7 样本 / 43 检查项，准确率标准误约 ±5%，不是大样本统计结论。
- 标准答案经过一轮校准（68.8% → 100%），在同一集合上调参有过拟合风险；抵消手段是 4 条独立真实语料回归断言。
- 夹具语境启发式**可被绕过**（把密钥写在带"示例"字样的注释旁会被判为夹具）。
- 关键词检查项无法判断语义正确性 —— 这部分必须由 `--llm-verdicts` 深审补充。
- 不解析 PDF / PPTX 内容（零依赖的代价，报告中已明示）。
- 提交包含刻意坏样本，**全量盲扫必然 FAIL**；留档而非删除（见上方警示）。

## 相关链接

- 基座：`wechat-doc-mapper.skill`（Elite20 官方技能）
- 本人 C4 提交：`challenge-submission-checker`（本技能的自检思路来源之一）
- 挑战原文：`参考资料/CHALLENGE.md`
