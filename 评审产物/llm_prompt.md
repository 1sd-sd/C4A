# C4A 深审 Prompt（规则层 → LLM 层）

生成时间：2026-10-05 00:12:28　｜　评审档位：`c4_four_conditions`

下面是规则层给出的**确定性初判与证据**。请你作为评审专家：
1. 逐条复核规则判定是否合理（尤其 ⚠️/❌ 的项）；
2. 指出规则可能误判的地方（例如把示例路径误判为硬编码）；
3. 给出你对该作者各维度的最终评级。

**输出格式（严格 JSON，不要多余文字）**：
```json
{"authors": {"<作者>": {"<维度id>": {"rating": "pass|partial|fail", "rationale": "一句话依据"}}}}
```

---

## 作者：lishengdan（规则层：92.5/100 · A）

- 完整性：齐全（5/5）（5/5，比率 1.0）
- **可复用**（reusable）规则判定：⚠️ score=0.5
    - [pass] 有安装 / 上手步骤 → 命中关键词：「安装」、「使用步骤」、「pip install」、「install」
    - [fail] 可执行文件内无硬编码绝对路径 → lishengdan/demo/lishengdan_C4_demo_生成脚本.py: D:\；lishengdan/demo/lishengdan_C4_demo_生成脚本.py: C:\
    - [partial] 文档内绝对路径仅作为示例且数量有限 → 文档出现 9 处绝对路径（阈值 4），与本机目录耦合偏重；lishengdan/lishengdan_C4_AI日志.md: D:/；lishengdan_C4_challenge-submission-checker.skill::challenge-submission-checker/SKILL.md: D:/；lishengdan_C4_challenge-submission-checker.skill::challenge-submission-checker/SKILL.md: D:/
    - [pass] 声明了运行环境 / 依赖 → 命中关键词：「环境要求」、「依赖」、「requirements」、「python 3」
    - [pass] 有平台兼容 / 泛化说明 → 命中关键词：「windows」、「macos」、「linux」、「平台无关」
- **可执行**（executable）规则判定：✅ score=1.0
    - [pass] 含可运行代码 / 工作流定义 → 包含 3 个代码文件/代码段
    - [pass] 技能包结构合法（.skill/zip 可解压且含 SKILL.md） → lishengdan_C4_challenge-submission-checker.skill：zip 格式、18 个条目、含 SKILL.md
    - [pass] Python 源码语法可解析 → 3 个 Python 文件 compile() 通过
    - [pass] SKILL.md 具备有效 YAML frontmatter（name + description） → lishengdan_C4_challenge-submission-checker.skill::challenge-submission-checker/SKILL.md：name=challenge-submission-checker，description 1024 字符
- **可验证**（verifiable）规则判定：✅ score=1.0
    - [pass] 有测试用例或可复跑示例 → 命中关键词：「测试」、「自测」、「test」、「断言」
    - [pass] 写明了预期输出 / 结果 → 命中关键词：「预期」
    - [pass] Demo 文件存在且非空 → lishengdan/demo/lishengdan_C4_demo_1_技能自测.png（43.9 KB）；lishengdan/demo/lishengdan_C4_demo_2_通过场景.png（91.3 KB）；lishengdan/demo/lishengdan_C4_demo_3_缺失交付物.png（108.0 KB）
    - [pass] 有明确的通过 / 失败判据 → 命中关键词：「pass」、「fail」、「判定」、「阈值」
- **IO 明确**（clear_io）规则判定：✅ score=1.0
    - [pass] 存在「输入 X，输出 Y」式一句话描述 → lishengdan/lishengdan_C4_AI日志.md：…输入输出…
    - [pass] 输入的类型 / 格式有说明 → 命中关键词：「输入」、「参数」、「argv」
    - [pass] 输出的类型 / 格式有说明 → 命中关键词：「输出」、「生成」、「产出」、「报告」
    - [pass] 说明了边界输入的处理 → 命中关键词：「边界」、「缺失」、「异常」、「edge case」
- 红旗：已排除测试夹具中的假密钥（透明记录，不扣分）

## 作者：c4a-starter（规则层：50/100 · D）

- 完整性：严重缺失（1/5，比率 0.3）
- **可复用**（reusable）规则判定：✅ score=1.0
    - [pass] 有安装 / 上手步骤 → 命中关键词：「安装」、「pip install」、「npm install」、「install」
    - [na] 可执行文件内无硬编码绝对路径 → —
    - [pass] 文档内绝对路径仅作为示例且数量有限 → 文档出现 2 处示例路径（≤4，视为示例）；c4a-starter/references/c4_rubric.yaml: /Users/；c4a-starter/references/c4_rubric.yaml: C:\
    - [pass] 声明了运行环境 / 依赖 → 命中关键词：「环境要求」、「依赖」、「requirements」、「dependencies」
    - [pass] 有平台兼容 / 泛化说明 → 命中关键词：「兼容」、「compatible」、「windows」、「macos」
- **可执行**（executable）规则判定：✅ score=1.0
    - [pass] 含可运行代码 / 工作流定义 → SKILL.md 内含有序工作流/步骤章节
    - [na] 技能包结构合法（.skill/zip 可解压且含 SKILL.md） → 未提交 .skill / 压缩包
    - [na] Python 源码语法可解析 → 未包含 Python 源码
    - [pass] SKILL.md 具备有效 YAML frontmatter（name + description） → c4a-starter/SKILL.md：name=c4-skill-evaluator，description 683 字符
- **可验证**（verifiable）规则判定：⚠️ score=0.5
    - [pass] 有测试用例或可复跑示例 → 命中关键词：「测试」、「test」、「示例」、「example」
    - [pass] 写明了预期输出 / 结果 → 命中关键词：「预期」、「expected」
    - [fail] Demo 文件存在且非空 → 未找到 demo 文件
    - [pass] 有明确的通过 / 失败判据 → 命中关键词：「pass」、「fail」
- **IO 明确**（clear_io）规则判定：✅ score=1.0
    - [pass] 存在「输入 X，输出 Y」式一句话描述 → c4a-starter/references/c4_rubric.yaml：…输入输出…
    - [pass] 输入的类型 / 格式有说明 → 命中关键词：「输入」、「input」、「接受」
    - [pass] 输出的类型 / 格式有说明 → 命中关键词：「输出」、「生成」、「报告」、「output」
    - [pass] 说明了边界输入的处理 → 命中关键词：「空文件夹」、「缺失」、「edge case」
- 红旗：核心交付物缺失、无 AI 使用记录、无 Demo

## 作者：skill-explainer（规则层：50/100 · D）

- 完整性：严重缺失（1/5，比率 0.3）
- **可复用**（reusable）规则判定：⚠️ score=0.5
    - [pass] 有安装 / 上手步骤 → 命中关键词：「install」
    - [na] 可执行文件内无硬编码绝对路径 → —
    - [partial] 文档内绝对路径仅作为示例且数量有限 → 文档出现 6 处绝对路径（阈值 4），与本机目录耦合偏重；skill-explainer.skill::skill-explainer/SKILL.md: /mnt/；skill-explainer.skill::skill-explainer/SKILL.md: /mnt/；skill-explainer.skill::skill-explainer/SKILL.md: /mnt/
    - [pass] 声明了运行环境 / 依赖 → 命中关键词：「requirements」
    - [fail] 有平台兼容 / 泛化说明 → —
- **可执行**（executable）规则判定：✅ score=1.0
    - [pass] 含可运行代码 / 工作流定义 → SKILL.md 内含有序工作流/步骤章节
    - [pass] 技能包结构合法（.skill/zip 可解压且含 SKILL.md） → skill-explainer.skill：zip 格式、2 个条目、含 SKILL.md
    - [na] Python 源码语法可解析 → 未包含 Python 源码
    - [pass] SKILL.md 具备有效 YAML frontmatter（name + description） → skill-explainer.skill::skill-explainer/SKILL.md：name=skill-explainer，description 797 字符
- **可验证**（verifiable）规则判定：⚠️ score=0.5
    - [pass] 有测试用例或可复跑示例 → 命中关键词：「test」、「示例」、「example」
    - [pass] 写明了预期输出 / 结果 → 命中关键词：「expected」
    - [fail] Demo 文件存在且非空 → 未找到 demo 文件
    - [pass] 有明确的通过 / 失败判据 → 命中关键词：「>=」
- **IO 明确**（clear_io）规则判定：✅ score=1.0
    - [pass] 存在「输入 X，输出 Y」式一句话描述 → skill-explainer.skill::skill-explainer/references/rubric.md：…input → processing → output…
    - [pass] 输入的类型 / 格式有说明 → 命中关键词：「input」
    - [pass] 输出的类型 / 格式有说明 → 命中关键词：「output」、「.md」
    - [pass] 说明了边界输入的处理 → 命中关键词：「边界」、「edge case」
- 红旗：核心交付物缺失、无 AI 使用记录、无 Demo

## 作者：wechat-doc-mapper（规则层：49.5/100 · D）

- 完整性：严重缺失（1/5，比率 0.3）
- **可复用**（reusable）规则判定：⚠️ score=0.5
    - [pass] 有安装 / 上手步骤 → 命中关键词：「上手」
    - [fail] 可执行文件内无硬编码绝对路径 → wechat-doc-mapper.skill::wechat-doc-mapper/scripts/wechat_doc_mapper.py: /mnt/；wechat-doc-mapper.skill::wechat-doc-mapper/scripts/wechat_doc_mapper.py: /mnt/
    - [pass] 文档内绝对路径仅作为示例且数量有限 → 文档出现 3 处示例路径（≤4，视为示例）；wechat-doc-mapper.skill::wechat-doc-mapper/SKILL.md: /mnt/；wechat-doc-mapper.skill::wechat-doc-mapper/SKILL.md: /mnt/；wechat-doc-mapper.skill::wechat-doc-mapper/SKILL.md: /mnt/
    - [pass] 声明了运行环境 / 依赖 → 命中关键词：「python 3」、「python3」
    - [fail] 有平台兼容 / 泛化说明 → —
- **可执行**（executable）规则判定：✅ score=1.0
    - [pass] 含可运行代码 / 工作流定义 → 包含 1 个代码文件/代码段
    - [pass] 技能包结构合法（.skill/zip 可解压且含 SKILL.md） → wechat-doc-mapper.skill：zip 格式、3 个条目、含 SKILL.md
    - [pass] Python 源码语法可解析 → 1 个 Python 文件 compile() 通过
    - [pass] SKILL.md 具备有效 YAML frontmatter（name + description） → wechat-doc-mapper.skill::wechat-doc-mapper/SKILL.md：name=wechat-doc-mapper，description 918 字符
- **可验证**（verifiable）规则判定：⚠️ score=0.5
    - [pass] 有测试用例或可复跑示例 → 命中关键词：「测试」、「example」
    - [pass] 写明了预期输出 / 结果 → 命中关键词：「expected」
    - [fail] Demo 文件存在且非空 → 未找到 demo 文件
    - [pass] 有明确的通过 / 失败判据 → 命中关键词：「pass」
- **IO 明确**（clear_io）规则判定：⚠️ score=0.5
    - [fail] 存在「输入 X，输出 Y」式一句话描述 → —
    - [fail] 输入的类型 / 格式有说明 → —
    - [pass] 输出的类型 / 格式有说明 → 命中关键词：「生成」、「output」、「.md」、「.json」
    - [pass] 说明了边界输入的处理 → 命中关键词：「edge case」
- 红旗：核心交付物缺失、无 AI 使用记录、无 Demo
