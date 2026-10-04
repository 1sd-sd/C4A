# lishengdan_C4_教学说明.md

> 教会一个**从没见过这个技能的人**在 3 分钟内跑起来，并避开我踩过的坑。

---

## 一、这个技能是干什么的（30 秒版）

你要交挑战作业。交之前你担心：文件齐了吗？命名对吗？`.skill` 包打得对吗？有没有忘了删的草稿和密钥？

这个技能回答这四个问题，并给你一个分数和一个"还缺什么"的清单。

**输入**：一个文件夹（+ 挑战定义文件，或一条交付物模式）
**输出**：`自检报告.md` + `check_result.json` + `提交清单.md` + 终端上的 PASS / WARN / FAIL

---

## 二、如何上手（3 分钟）

### Step 0 — 环境要求

- Python **3.9 及以上**（检查：`python --version`）
- **不需要 pip install 任何东西**——只用标准库。这是刻意设计，为了保证任何人拿过去就能跑。
- Windows / macOS / Linux 都行（脚本内部处理了中文路径和 Windows 控制台编码）。

### Step 1 — 拿到技能

任选其一：

```bash
# 方式 A：从 .skill 包解压（推荐，这就是"安装"）
python -c "import zipfile; zipfile.ZipFile('lishengdan_C4_challenge-submission-checker.skill').extractall('.')"

# 方式 B：直接用源码目录 src/challenge-submission-checker/
```

如果你在用 Claude / WorkBuddy 这类支持技能的 Agent：把解压出的
`challenge-submission-checker/` 文件夹放进技能目录
（WorkBuddy 是 `~/.workbuddy/skills/`），然后对 Agent 说
"**帮我检查一下这个提交文件夹**"即可触发。

### Step 2 — 先跑自测，确认技能没坏（强烈建议）

```bash
cd challenge-submission-checker
python examples/run_selftest.py
```

看到三行 `[PASS]` 就说明环境 OK：

```
 [PASS] demo-pass      判定=PASS  总分=91.8   阻断=0
 [PASS] demo-missing   判定=FAIL  总分=69.5   阻断=2
 [PASS] demo-dirty     判定=FAIL  总分=36.3   阻断=4
```

### Step 3 — 检查你自己的提交文件夹

```bash
python scripts/check_deliverables.py --pack "你的提交文件夹" --author 你的ID
```

只要你的文件夹（或它的父目录）里有 `challenge.json` / `challenge.yaml`，脚本会**自动**读取交付物模式，不用手动指定。

没有挑战定义文件？直接给模式：

```bash
python scripts/check_deliverables.py --pack ./out --pattern "*skill说明*,*.skill,*demo*,*AI日志*"
```

### Step 4 — 读结果、修、重跑

- 终端：看 `>>> 总分 xx / 100   判定：XXX`
- 详细：打开 `<pack>/_selfcheck/自检报告.md`
- 修完 → **再跑一次** → 从 FAIL 变 PASS 才算完。

脚本**只读不改**，重跑多少次都安全。

---

## 三、常见坑（我和测试者真实踩过的）

### 坑 1：路径带空格没加引号
```bash
python check_deliverables.py --pack D:/我的 挑战/提交     # ❌ 会被拆成两个参数
python check_deliverables.py --pack "D:/我的 挑战/提交"   # ✅
```

### 坑 2：`*.skill` 压缩时多套了一层目录
`.skill` 是 zip，**顶层必须直接是技能文件夹**（里面才是 `SKILL.md`）。
用"右键文件夹 → 压缩"经常会把文件夹包在外面，或者反过来把散文件压在根上。
判定标准：解压后第一层能看到 `challenge-submission-checker/SKILL.md`。

### 坑 3：`SKILL.md` 的 `description` 写得太短
少于 60 字符会被扣分。更重要的是：**description 决定技能会不会被触发**。
写法 = "做什么 + 什么时候用 + 5 个以上中英文触发短语"。参考本技能包里的写法。

### 坑 4：`~$xxx.docx` 这种 Office 锁文件被当成交付物
v1.0 真的犯过这个错——锁文件 `~$lishengdan_C4_skill说明.docx` 命中了 `*skill说明*`，
把"齐全度"刷成假的 80%。v1.1 已修复（草稿/锁文件在匹配前就被剔除）。
如果你用的是旧版，遇到"明明缺文件却显示齐全"就是这个原因。

### 坑 5：报告写进了被检查的文件夹，第二次检查时被当成草稿
默认输出到 `<pack>/_selfcheck/`，里面的 `check_result.json` 会被 `_*` 规则命中（`_selfcheck` 不命中，但 `_*` 文件会）。
**解决办法**：用 `--out` 把报告写到被检文件夹**外面**。

### 坑 6：把技能源码和测试样例一起放进提交文件夹
样例里**故意**放了假密钥和空壳文件（用于自测），会被当成真问题报出来。
**解决办法**：加 `--exclude src/challenge-submission-checker/examples`。

### 坑 7：Windows 控制台中文乱码
脚本已强制 UTF-8 输出。如果你在更老的 cmd 里仍看到乱码，先执行 `chcp 65001`。

### 坑 8：以为"文件存在"就够了
一个 26 字节的 `skill说明.md` 和没有它，在评审眼里是一回事。
脚本会把 <32 字节的文件判为空壳（0 分、阻断项），别指望蒙混。

---

## 四、优化技巧

1. **接进流水线做卡点**（最推荐）
   ```bash
   python scripts/check_deliverables.py --pack ./out --json-only > r.json \
     || (echo "自检未通过，停止上传" && exit 1)
   ```
   退出码语义：`0` = 通过；`1` = FAIL；`2` = 用法错误。

2. **正式提交前跑一次 `--strict`**
   把"建议项"也升级为阻断项。平时 WARN 能过，严格模式会逼你把建议章节补齐。

3. **自定义章节规则不改代码**
   编辑 `references/doc_rules.yaml`，往 `required` / `recommended` 里加关键词即可。
   比如你想强制所有说明文档必须有"安装"一节，加一行就行。

4. **换一套交付物模式，技能立刻服务另一个挑战**
   C2 论文、C5 仓库、C6 网页……只要改 `--pattern`，不用改代码。

5. **把 `提交清单.md` 直接当提交说明**
   它是勾选式的，交给评审时一目了然。

6. **想让分数更严？**
   权重和阈值全部写在 `references/scoring.md`，和脚本内置值一一对应，可以按需改脚本顶部常量。

---

## 五、30 秒判断"我的技能能不能也这么交付"

对照四条件自查：

| 条件 | 本技能的自证方式 |
|---|---|
| 可复用 | 解压到全新空目录 + 零依赖 → 自测套件全过（案例 5） |
| 可执行 | 不是文档，是 781 行可运行脚本 |
| 可验证 | 3 个固定样例 + 断言，`python examples/run_selftest.py` 退出码说话 |
| IO 明确 | 输入一个文件夹路径，输出"缺什么、几分、能不能交" |

你的技能只要能填满这四格，就达到了同样的交付标准。

---

## 六、一分钟答疑

**Q：会修改我的文件吗？**
不会。脚本全程只读，产物写到 `_selfcheck/`（可用 `--out` 改到别处）。

**Q：支持中文文件名吗？**
支持，全程按 UTF-8 处理；Windows 的 GBK 控制台也已适配。

**Q：模式里的 `*` 是什么意思？**
标准通配符：`*.skill` = 以 `.skill` 结尾；`*demo*` = 文件名含 "demo"。匹配大小写不敏感，子目录里的文件也算。

**Q：为什么我的 `.skill` 被扣了 10 分？**
看报告"文件体检"表里的备注。最常见：`description 过短` 或 `SKILL.md 缺 frontmatter`。
