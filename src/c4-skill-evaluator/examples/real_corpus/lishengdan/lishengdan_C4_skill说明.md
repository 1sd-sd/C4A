# lishengdan_C4_skill说明.md

> **技能名**：challenge-submission-checker（挑战提交自检器）
> **一句话**：**输入**一个提交文件夹（+ 挑战定义文件或交付物模式），**输出**一份带 0–100 分和"还缺什么"清单的提交自检报告。
> **版本**：v1.2.0 ｜ 零第三方依赖 ｜ Python 3.9+

---

## 一、解决什么问题

挑战提交有一个反复出现的失败模式：**你以为交齐了，其实没有。**

| 真实发生的翻车 | 后果 |
|---|---|
| 交付物模式是 `*skill说明*,*.skill,*教学说明*,*demo*,*AI日志*`，五类少交一类 | 直接被判定"核心交付物缺失" |
| 文件在，但只有 26 字节，里面写着"TODO 待补充" | 空壳文件，比不交更难看 |
| `.skill` 压缩时多套了一层目录 / `SKILL.md` 少了 frontmatter / `description` 太短 | 技能装上后**永远不会被触发**，等于没交 |
| 目录里混进 `_tmp.json`、`~$草稿.docx` | 显得不专业，还可能被当成草稿评审 |
| 提交前忘了删带 API Key 的调试日志 | 泄露凭据，代价最大的一类错误 |

这些问题的共同点是：**靠人脑记清单不可靠，而它们全部可以被规则判定。**

本技能把"提交前自检"从记忆里搬进脚本——给定文件夹 X，输出合规判定 Y，同一份输入永远得到同一个结论。

## 二、使用场景

- **每次挑战提交前**：跑一次，确认交付物齐全、命名规范、没有垃圾文件。
- **打包 `.skill` 之后**：验证包结构合法（zip 可解压、`SKILL.md` 有 frontmatter、`name` 是 kebab-case、`description` 足够长、正文 ≤ 500 行）。
- **接进自动化流水线**：`--json-only` 输出结构化 JSON + 非零退出码，可以做"自检不过就停止上传"的卡点。
- **收到别人的提交包**：先扫一遍再评审，跳过明显不合格的。
- **教学场景**：作为"什么叫可验证交付物"的活教材——它本身就是一个四条件齐全的技能。

## 三、输入 / 输出

### 输入

| 参数 | 必填 | 说明 |
|---|---|---|
| `--pack <目录>` | ✅ | 要检查的提交文件夹 |
| `--challenge <file>` | 二选一 | `challenge.json` 或 `challenge.yaml`（脚本会在 pack 及其父目录**自动探测**） |
| `--pattern "<通配串>"` | 二选一 | 直接给交付物模式，如 `"*skill说明*,*.skill,*demo*,*AI日志*"` |
| `--author <ID>` | 可选 | 命名规范检查：文件名应包含作者标识 |
| `--title` | 可选 | 报告标题 |
| `--exclude <目录>` | 可选，可重复 | 排除干扰目录（如技能自己的测试样例） |
| `--out <目录>` | 可选 | 报告输出位置，默认 `<pack>/_selfcheck/` |
| `--json-only` / `--strict` / `--quiet` | 可选 | 机器可读 / 严格模式 / 静默 |

### 输出（固定三份文件 + 终端摘要）

| 文件 | 给谁看 |
|---|---|
| `自检报告.md` | 人：结论、五维得分表、交付物匹配表、文件体检表、问题清单 |
| `check_result.json` | 程序/CI：完整结构化结果 |
| `提交清单.md` | 直接当提交说明用：勾选式清单 + 交付物明细 |

**IO 一句话**：输入一个文件夹路径，输出"缺什么、错什么、几分、能不能交"。

## 四、检查项与评分

| 维度 | 权重 | 检查内容 |
|---|---|---|
| 交付物齐全度 | 35 | 每个模式 token 是否至少命中 1 个文件 |
| 内容质量 | 25 | 空壳文件（<32B）、占位符（TODO/待补充）、Markdown 必需章节 |
| 技能包完整性 | 20 | `.skill` 解剖：zip 合法性、SKILL.md、frontmatter、kebab-case、description 长度、500 行上限 |
| 目录卫生 | 10 | `_*` 草稿、`~$*` 锁文件、`.DS_Store`、`*.bak/*.tmp` |
| 敏感信息 | 10 | API Key / Token / 私钥 / 硬编码口令（一票否决） |

判定：`≥85 且无阻断项 → PASS`；`60–84 → WARN`；`<60 或有阻断项 → FAIL`。
若模式里没有 `.skill`，`packaging` 权重自动重分配，不会因"不适用"被扣分。

## 五、使用步骤

```bash
# 1. 拿到技能（任选其一）
#    a) 解压 lishengdan_C4_challenge-submission-checker.skill 到你的技能目录
#    b) 直接用 src/challenge-submission-checker/ 里的源码

# 2. 最常用：一条命令自检
python scripts/check_deliverables.py --pack "D:/我的挑战/C4提交" --author lishengdan

# 3. 看终端结论，或打开 <pack>/_selfcheck/自检报告.md

# 4. 按报告修复 → 重跑 → 直到 PASS

# 5.（可选）验证技能本身没坏
python examples/run_selftest.py
```

## 六、真实案例

### 案例 1：齐全的提交 → PASS（91.8 分）

对 `examples/demo-pass`（5 个交付物、合法 `.skill` 包）运行：

```
[OK] *skill说明*   命中 1 个
[OK] *.skill       命中 1 个
[OK] *教学说明*     命中 1 个
[OK] *demo*        命中 2 个
[OK] *AI日志*      命中 1 个
>>> 总分 91.8 / 100   判定：PASS      退出码 0
```

### 案例 2：缺两个交付物 → FAIL，并点名缺什么

对 `examples/demo-missing` 运行：

```
[XX] *教学说明*   命中 0 个
[XX] *AI日志*     命中 0 个
阻断项：
  [XX] 缺少交付物：*教学说明*
  [XX] 缺少交付物：*AI日志*
>>> 总分 69.5 / 100   判定：FAIL      退出码 1
```

### 案例 3：空壳文件 + 假密钥 + 草稿 → FAIL，安全维度归零

对 `examples/demo-dirty` 运行，`safety = 0`，阻断项同时报出
"文件过小（26 B）疑似空壳" 与 "疑似敏感信息泄露"。详见 `demo/lishengdan_C4_demo_4_脏数据与密钥.png`。

### 案例 4：技能包自检（吃自己的狗粮）

用本技能检查它自己的 `.skill` 包：包结构评分 **100/100**
（18 个条目、根目录 `challenge-submission-checker`、SKILL.md 169 行、description 1024 字符）。

### 案例 5：可复用性实测（模拟陌生人安装）

把 `.skill` 解压到一个**全新的空目录**，在没有任何环境配置的情况下运行自测套件 → 三个用例全部通过。
（这就是"可复用"的机器证明：零依赖、零配置、确定性输出。）

## 七、边界与不做的事

- 只判"齐不齐、像不像、有没有明显硬伤"，**不判断内容写得好不好**（那是评审的事）。
- 不修改被检目录的任何文件，不自动补文件、不自动改名。
- 不联网。
- 完整边界情况清单见技能包内 `SKILL.md` 的 Edge Cases 一节。

## 八、技能包结构

```
challenge-submission-checker/
├── SKILL.md                      主指令：工作流 + 检查项 + 边界情况 + 示例（169 行）
├── scripts/
│   └── check_deliverables.py     确定性检查脚本（零第三方依赖，781 行）
├── references/
│   ├── doc_rules.yaml            Markdown 章节规则（YAML 驱动，可加规则不改代码）
│   └── scoring.md                评分标准全公开，任何人可核对分数怎么算的
└── examples/
    ├── demo-pass/                齐全样例 → 应 PASS
    ├── demo-missing/             缺失样例 → 应 FAIL
    ├── demo-dirty/               脏数据样例 → 应 FAIL
    └── run_selftest.py           一条命令的自测套件（带断言）
```

三层加载：`name+description`（触发）→ `SKILL.md` 正文（执行）→ `references/`（按需加载）。
