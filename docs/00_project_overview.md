# 项目概览

**状态：原多模态方向停止，E003 双时钟 CPU 验证完成但未通过推进门槛。** 有界 cohort、
删失标签、无特征与年龄控制、双时钟历史及 CPU 比较均已在 UCSF 完成。测试集仍封存，
未启动神经模型或 GPU 实验。诊断、实验室和生理状态仍因缺少 availability 语义而禁用。
Mac 现在负责代码、合成验证和研究审查；真实数据及验证仍留在 UCSF。

Intent–Execution–State Modeling 研究一个可被否定的问题：在相同信息、参数量和
训练预算下，显式区分临床意图、实际执行、后续观测，是否能改善患者表示与时间预测？
工作标题：Learning Patient Representations by Disentangling Clinical Intentions,
Executed Interventions, and Physiological Observations。

医嘱并不保证执行，但给事件加不同 type embedding 本身不是足够的新意。
候选贡献是 order-conditioned execution dynamics、删失及竞争事件的显式建模，
以及对工作流变化的泛化。当前未证实任何一项收益。

Phase 0 建立合成数据和 Git 交接；Phase 1 已验证双时间医嘱／给药可用性。缩窄后的
Phase 2 已完成固定特征的单时钟与双时钟 workflow 比较，未通过推进门槛。
新的研究设计须与已结束的 E003 分开，不恢复未满足语义条件的多模态任务。
当前完成标准是可运行、可追溯、无患者重叠、无未来信息，而不是取得更高分数。
研究目标为 MICCAI Main / MLHC；只有方法贡献可推广且证据充分时才考虑其他会议。
不承诺发表、实验优势或八周内完成临床研究。
