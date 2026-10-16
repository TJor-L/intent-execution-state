# 项目概览

**最终可行性状态：停止于 Phase 1，不进入 Phase 2。** 有界 cohort、删失标签管线、
无特征基线与年龄特征控制均已在 UCSF 完成。新增诊断、实验室或历史事件缺少经审核的
发生时间／可用时间语义，无法保证 point-in-time 正确性。继续方法比较会把潜在未来信息
泄漏当作预测信号，因此项目按预设停止规则收束为负面可行性结果。

Intent–Execution–State Modeling 研究一个可被否定的问题：在相同信息、参数量和
训练预算下，显式区分临床意图、实际执行、后续观测，是否能改善患者表示与时间预测？
工作标题：Learning Patient Representations by Disentangling Clinical Intentions,
Executed Interventions, and Physiological Observations。

医嘱并不保证执行，但给事件加不同 type embedding 本身不是足够的新意。
候选贡献是 order-conditioned execution dynamics、删失及竞争事件的显式建模，
以及对工作流变化的泛化。当前未证实任何一项收益。

Phase 0 建立合成数据和 Git 交接；Phase 1 验证真实数据可用性；Phase 2 原计划做方法比较，
但因 Phase 1 的特征语义退出条件未满足而取消。
当前完成标准是可运行、可追溯、无患者重叠、无未来信息，而不是取得更高分数。
研究目标为 MICCAI Main / MLHC；只有方法贡献可推广且证据充分时才考虑其他会议。
不承诺发表、实验优势或八周内完成临床研究。
