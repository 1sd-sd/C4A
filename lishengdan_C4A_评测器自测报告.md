# c4-skill-evaluator 自测报告（准确率 / 误判率）

> 生成时间：2026-10-05 00:12:30　｜　档位：`c4_four_conditions`　｜　样本：合成评测集 7 份 / 检查项 43 项

## 一、结论

| 指标 | 数值 |
|------|------|
| 检查项通过 | 43 / 43 |
| **准确率** | **100.0%** |
| **误判率** | **0.0%** |
| 阈值 | 95% → PASS |
| 真实语料回归断言 | 4/4 通过 |

## 二、逐项明细

| 样本 | 检查项 | 期望 | 实际 | 结果 |
|------|--------|------|------|------|
| zhangwei | 完整性(命中数) | 5 | 5 | ✅ |
| zhangwei | 红旗-召回(必须命中) | [] | [] | ✅ |
| zhangwei | 红旗-精度(不得误报) | ['fake_package', 'hollow_file', 'junk_fi | [] | ✅ |
| zhangwei | 维度评级:reusable | pass | pass | ✅ |
| zhangwei | 维度评级:executable | pass | pass | ✅ |
| zhangwei | 维度评级:verifiable | pass | pass | ✅ |
| zhangwei | 维度评级:clear_io | pass | pass | ✅ |
| liming | 完整性(命中数) | 3 | 3 | ✅ |
| liming | 红旗-召回(必须命中) | ['missing_artifacts', 'no_ai_log', 'no_d | ['missing_artifacts', 'no_ai_log', 'no_d | ✅ |
| liming | 红旗-精度(不得误报) | ['fake_package', 'hollow_file', 'secret_ | [] | ✅ |
| liming | 维度评级:reusable | pass | pass | ✅ |
| liming | 维度评级:executable | pass | pass | ✅ |
| liming | 维度评级:verifiable | partial | partial | ✅ |
| liming | 维度评级:clear_io | pass | pass | ✅ |
| wangxiao | 完整性(命中数) | 2 | 2 | ✅ |
| wangxiao | 红旗-召回(必须命中) | ['fake_package', 'hollow_file', 'missing | ['fake_package', 'hollow_file', 'missing | ✅ |
| wangxiao | 红旗-精度(不得误报) | ['secret_leak'] | [] | ✅ |
| wangxiao | 维度评级:reusable | fail | fail | ✅ |
| wangxiao | 维度评级:executable | fail | fail | ✅ |
| wangxiao | 维度评级:verifiable | fail | fail | ✅ |
| wangxiao | 维度评级:clear_io | fail | fail | ✅ |
| zhaolei | 完整性(命中数) | 1 | 1 | ✅ |
| zhaolei | 红旗-召回(必须命中) | ['missing_artifacts', 'no_ai_log', 'no_d | ['missing_artifacts', 'no_ai_log', 'no_d | ✅ |
| zhaolei | 红旗-精度(不得误报) | ['fake_package', 'hollow_file', 'secret_ | [] | ✅ |
| zhaolei | 维度评级:reusable | pass | pass | ✅ |
| zhaolei | 维度评级:clear_io | pass | pass | ✅ |
| sunqi | 完整性(命中数) | 5 | 5 | ✅ |
| sunqi | 红旗-召回(必须命中) | ['secret_leak'] | ['secret_leak'] | ✅ |
| sunqi | 红旗-精度(不得误报) | ['fake_package', 'hollow_file'] | [] | ✅ |
| sunqi | 维度评级:reusable | partial | partial | ✅ |
| sunqi | 维度评级:executable | partial | partial | ✅ |
| chenhao_v1 | 完整性(命中数) | 3 | 3 | ✅ |
| chenhao_v1 | 红旗-召回(必须命中) | ['missing_artifacts', 'no_ai_log'] | ['missing_artifacts', 'no_ai_log'] | ✅ |
| chenhao_v1 | 红旗-精度(不得误报) | ['fake_package', 'hollow_file', 'secret_ | [] | ✅ |
| chenhao_v1 | 维度评级:executable | pass | pass | ✅ |
| chenhao_v2 | 完整性(命中数) | 5 | 5 | ✅ |
| chenhao_v2 | 红旗-召回(必须命中) | [] | [] | ✅ |
| chenhao_v2 | 红旗-精度(不得误报) | ['fake_package', 'hollow_file', 'missing | [] | ✅ |
| chenhao_v2 | 维度评级:reusable | pass | pass | ✅ |
| chenhao_v2 | 维度评级:executable | pass | pass | ✅ |
| chenhao_v2 | 维度评级:verifiable | pass | pass | ✅ |
| chenhao_v2 | 维度评级:clear_io | pass | pass | ✅ |
| chenhao | 版本追踪 | 识别出多版本且方向符合预期 | [50, 100.0] | ✅ |

## 三、真实语料回归断言（独立于合成集的对照校验）

| 断言 | 实际 | 结果 |
|------|------|------|
| 真实提交 lishengdan 应判 5/5 完整 | 5 | ✅ |
| 真实提交 lishengdan 无 critical/high 红旗（夹具假密钥不得误报） | [] | ✅ |
| 真实技能包（非 C4 提交）应被判缺失 4 类交付物 | {'c4a-starter': 1, 'skill-explainer': 1, 'wechat-doc-mapper' | ✅ |
| 确定性：同一输入两次运行结果逐字节一致 | 一致 | ✅ |

## 四、已知局限（诚实披露）

1. 夹具集只有 7 个样本 / 43 个检查项，准确率的标准误约 ±5%，不是统计意义上的大样本评测。
2. 标准答案经过一轮校准：初始版本（按直觉填写期望值）只有 68.8%，逐条复盘后修正了 10 处偏差（其中 3 处是评审器真实缺陷、7 处是期望值本身推导错误）。在同一集合上调参存在过拟合风险，抵消手段是上表 real_corpus 的独立回归断言。
3. 安全检测依赖『夹具语境』启发式：把密钥写在带 sample/示例 字样的注释旁会被判为夹具而放过，属已知可绕过点。
4. 关键词类检查项无法判断语义正确性（例如文档声称『支持任意路径』但代码并不支持）。本套件证明了纯规则的边界：skill-explainer 的 `tarfile.open('r:gz')` 解 zip 这类『代码与事实不符』的问题必须由 LLM 层发现。
