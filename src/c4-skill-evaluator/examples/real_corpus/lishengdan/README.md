# C4 技能分享与传播 · 提交包

> 挑战 ID：ch-20260717031424-4cdgor ｜ 作者：lishengdan ｜ 技能版本：v1.2.0

## 我交的是什么

**challenge-submission-checker（挑战提交自检器）**

> 一句话：**输入**一个提交文件夹（+ 挑战定义或交付物模式），**输出**一份带 0–100 分和
> "还缺什么"清单的自检报告。零第三方依赖，Python 3.9+ 直接跑。

它解决的是每个同学每次提交都会遇到的问题：**你以为交齐了，其实没有。**

## 交付物清单

| 挑战要求 | 文件 | 说明 |
|---|---|---|
| Skill 说明文档 | `lishengdan_C4_skill说明.md` | 问题、场景、IO、步骤、5 个真实案例 |
| 可执行内容 | `lishengdan_C4_challenge-submission-checker.skill` | 可安装技能包（zip 格式，24 KB / 18 个文件） |
| Demo | `demo/lishengdan_C4_demo_1..5_*.png` | 5 张**真实运行输出**渲染的终端截图 |
| 教学说明 | `lishengdan_C4_教学说明.md` | 3 分钟上手 + 8 个常见坑 + 优化技巧 |
| AI 日志 | `lishengdan_C4_AI日志.md` | 7 轮迭代全记录，含 3 个真问题的发现与修复 |
| 复盘 AAR | `lishengdan_C4_复盘AAR.md` | 问题根因、失败经验、5 条可执行改进 |
| 自检证据 | `lishengdan_C4_自检报告.md` | 用本技能检查本提交包的机器生成报告：**98.3 / 100，PASS** |

## 30 秒验证（不用信我，跑一下）

```bash
# 1. 解压技能包到任意空目录
python -c "import zipfile; zipfile.ZipFile('lishengdan_C4_challenge-submission-checker.skill').extractall('.')"
cd challenge-submission-checker

# 2. 一条命令自测（3 个固定样例 + 断言）
python examples/run_selftest.py
```

预期输出（三个用例全过，退出码 0）：

```
 [PASS] demo-pass      判定=PASS  总分=91.8   阻断=0
 [PASS] demo-missing   判定=FAIL  总分=69.5   阻断=2
 [PASS] demo-dirty     判定=FAIL  总分=36.3   阻断=4
```

然后检查你自己的提交文件夹：

```bash
python scripts/check_deliverables.py --pack "你的提交文件夹" --author 你的ID
```

## 目录结构

```
C4技能分享/
├── README.md                                  ← 本文件
├── lishengdan_C4_skill说明.md
├── lishengdan_C4_challenge-submission-checker.skill
├── lishengdan_C4_教学说明.md
├── lishengdan_C4_AI日志.md
├── lishengdan_C4_复盘AAR.md
├── lishengdan_C4_自检报告.md                  ← 本提交包的机器自检证据（98.3/100 PASS）
├── demo/                                      ← 5 张真实运行截图 + 出图脚本 + 原始输出
└── src/challenge-submission-checker/          ← 技能源码（与 .skill 包内容一致）
    ├── SKILL.md
    ├── scripts/check_deliverables.py
    ├── references/{doc_rules.yaml, scoring.md}
    └── examples/{demo-pass, demo-missing, demo-dirty, run_selftest.py}
```

## 四条件的自证

| 条件 | 自证方式 |
|---|---|
| **可复用** | 解压到全新空目录 + 零依赖 → 自测套件全过（实测记录见 AI 日志第 6 轮） |
| **可执行** | 不是文档，是 781 行可运行脚本 + 断言式自测套件 |
| **可验证** | 同一输入永远同一输出；`run_selftest.py` 用退出码说话 |
| **IO 明确** | 输入一个文件夹路径，输出"缺什么、几分、能不能交" |

## 欢迎试用和反馈

这是我的 C4 技能——**提交前自检**：输入你的提交文件夹路径，就能得到"还缺什么、有什么错、几分、能不能交"。
欢迎直接跑 `examples/run_selftest.py` 验证，然后把你的提交文件夹丢给它试试，反馈直接发群里。
