# Intent–Execution–State Modeling

> **研究状态（2026-10-19）：E003 未通过推进门槛，A001 不支持当前数据上的时间配对研究。** 原多模态／生理状态方向因
> 缺少新增来源的 point-in-time availability 语义而停止。缩窄后的双时钟 CPU 比较未达到
> 预设的收益和不确定性要求；测试集未开启，神经网络／GPU 实验未启动。本地正在进行
> 实现核验和研究审查；当前保留训练历史缺少独立时钟变化，不安排配对模型继任实验。
> 用户已授权转向固定数据的 W001：单时钟工作流预测，比较历史数量、时间分布和事件类型
> 的增量信息。实验室、诊断和未审核来源仍禁用。

**Mac 负责主要开发、合成测试与研究审查，UCSF 保留真实数据验证。** 用户可在服务器
提交准备好的 Slurm 命令，无需每次使用服务器 Codex。按里程碑通过 Git 同步。
本地不通过 SSH 访问 UCSF，不传回患者级数据。

Phase 0 已提供可执行研究基础设施、有界 cohort、两个私有 CPU 管线控制，以及
完整来源扫描后的双时钟历史和固定特征 CPU 比较。
它不证明结构化模型优于普通时序模型，也不包含真实 UCSF 字段映射或可披露临床结果。

## 本地快速开始

需要 Python 3.11+ 和 uv。此工作区已安装项目内 uv；Makefile 自动发现它。
新机器可按 [uv 官方说明](https://docs.astral.sh/uv/getting-started/installation/)
安装，或运行 `python3 -m pip install --target .tools uv`，无需更改系统 Python。

```bash
make setup        # uv sync --locked，安装锁定依赖及项目环境
make check        # Ruff、测试、Git 文件边界检查
make demo         # 新建独立运行目录，生成 → 校验 → cohort → 训练 → 评估
make pairing-demo # 合成时间配对机制：三模型 × 三情形 × 三个预设种子
make pairing-stress # 增加时间尺度对照、相同时钟情形与固定模型的延迟扰动
```

已安装全局 uv 时也可直接运行：

```bash
uv sync --locked
uv run ies run --config configs/synthetic.yaml
uv run pytest
```

每次实验写入 `artifacts/synthetic/<唯一运行编号>/`，包括配置、Git 版本、依赖版本、
文件校验和、事件、cohort、模型、预测、验证集及测试集指标。实验目录不会被覆盖，
运行失败会记录失败状态。所有输出均有 synthetic 标记，且默认不进入 Git。

`make pairing-demo` 使用 `configs/synthetic_pairing.yaml`，生成全部输入和结局，
比较时间汇总、同维度非配对对照和保留配对的联合时间特征。包含配对信号、无信号和
打乱配对三种情形；不接受外部 cohort/history 输入，也不连接 UCSF。
每次输出 `config.json`、`models.json`、`metrics.json` 与含源码摘要的 `manifest.json`。
它检验时间配对机制的可学习性，不能作为临床效果或开启测试集的依据。

`make pairing-stress` 保留原 S001 配置，另外运行 S002：增加同维度的单时钟衰减尺度
扩展对照、相同时钟情形，以及 1/4/8 小时的可用时间延迟；不在扰动后重训。
报告同时包含模型间差异和每个模型相对于自身未扰动结果的变化，完整保留失败情形。

服务器端的 `clock-audit` 已通过生成数据测试；用户回传 UCSF job `39325` 在提交
`14b8d69` 上完成，监控器的产物校验通过。后续定性反馈不支持现有保留训练历史上的
时钟配对对照；不重复运行，不据此开启新的临床模型。它只审计已有
训练历史的时间变化，不拟合新模型、不投影结局列，也不重扫原始临床来源。
工具支持匹配产物的有界自动发现和 Slurm 监控，操作见[服务器审计步骤](docs/16_remote_development.md)。

`make workflow-demo` 运行 W001 的四种生成机制、三个固定种子。新 `workflow-cv` 入口
复用已有 cohort/history，只在原训练患者内做五折交叉验证，比较无特征、历史数量、
合并类型的时间分布、区分类型的时间分布。原验证集和测试集不参与此轮分析。
本地实现和生成验证已完成；真实 W001 运行尚未发生。无需增加或修改来源数据，也不
依赖进一步解释字段。固定配置、对照、探索性解释和后续边界见 docs/11；服务器步骤见 docs/16。

独立步骤（输出路径必须尚不存在）：

```bash
uv run python scripts/generate_synthetic.py
uv run python scripts/validate_schema.py
uv run ies build-cohort --events artifacts/synthetic/events.parquet --output artifacts/synthetic/cohort.json
uv run ies train --cohort artifacts/synthetic/cohort.json --output artifacts/synthetic/model.json
uv run ies evaluate --cohort artifacts/synthetic/cohort.json --model artifacts/synthetic/model.json --output-dir artifacts/synthetic/evaluation
```

## 本地开发与服务器验证

1. Mac 在生成的数据上实现、复现和修复；同一分支保持一个主要写入方。
2. 编辑时运行针对性测试；pipeline 变更完成后运行 `make check`、`make demo`。
3. 用户明确要求后才 commit/push。真实任务需要新版本时，交付具体命令、输入绑定、
   资源范围及验收条件；用户在服务器拉取已发布代码并提交 Slurm。
4. 真实任务绑定实际干净提交；排队／运行任务使用的源码和配置不能修改，开发使用
   独立 checkout。现有环境、私有映射和获准产物优先复用。
5. Git 仅同步代码和审核后的操作摘要。E003 已结束；当前本地修复不需要重跑临床任务，
   不调整其门槛，不开启测试集，也不恢复未审核数据源。

提示词模板见 [docs/server_codex_prompt.md](docs/server_codex_prompt.md)，
操作细节见 [docs/16_remote_development.md](docs/16_remote_development.md)。
Git 仓库只承载代码、文档、合成测试及空白配置；schema 报告和真实结果留在服务器。

## 已完成的关联读取基础

服务器的两次小规模任务产出了有效 `limited` 报告，但独立来源前缀之间没有相同
身份覆盖；这不能证明缺少真实关联。后续已完成一致来源准备和验证。
历史过程见[服务器发现](docs/24_bounded_run_findings.md)与[关联访问设计](docs/25_coherent_access_design.md)。
服务器能力复核未发现保留精确医嘱—给药及 encounter 身份的现成索引；现有患者分片
MEDS 产物不能满足该验证器。现已实现 `coherent_manifest` 后端：它只读取经审核 manifest
中列出的 Parquet 文件和 row group，并分别限制扫描行、row-group 字节、保留行和 seed 键。
真实运行需要绑定当前私有映射与不可变快照、且证明三来源覆盖完整的服务器本地 manifest。
经单独授权的全源准备作业已在 UCSF 生成该私有 manifest，并完成一次无截断的 coherent
验证；所有真实产物和计数仍留在服务器。不重复没有变化的前缀扫描。

现有 v2 验证器使用服务器本地审核过的字段映射，关联医嘱、给药和独立观测覆盖来源，拒绝患者不一致或重复给药，
单独统计 encounter 不一致，并区分首次执行、已知终止与右删失。不读取检验特征，
不生成患者级 cohort。详见 [映射与计数规则](docs/22_bounded_feasibility.md)。

配置升级为 `schema_version: 2`，旧配置须参考新版模板在服务器重新审核。
无时区时间须声明审核过的 IANA 时区或共同移位时钟；夏令时歧义默认拒绝。
给药时间相等假设须附审核依据和回填分类规则，回填／未知分类拒绝整个关联医嘱。
观测结束使用独立来源的发生与可用时间，不用医嘱终止时间替代。

仅在 UCSF 填写被忽略的 `configs/feasibility.local.yaml` 后运行：

```bash
uv run python scripts/server.py plan feasibility --mapping configs/feasibility.local.yaml
```

一致访问的服务器本地 manifest 审核完成后，使用：

```bash
uv run python scripts/server.py plan feasibility \
  --mapping configs/feasibility.local.yaml \
  --access-manifest configs/coherent_access.local.yaml
```

空白结构见 `configs/coherent_access.example.yaml`；填充值、路径、审核引用和摘要均不得提交。

当且仅当全源准备已被单独批准时，可从干净提交通过 Slurm 运行：

```bash
uv run python scripts/server.py plan coherent-prepare \
  --config configs/remote.local.yaml \
  --mapping configs/feasibility.v2.local.yaml
uv run python scripts/server.py submit coherent-prepare \
  --config configs/remote.local.yaml \
  --mapping configs/feasibility.v2.local.yaml
```

准备器完整扫描三来源的映射投影列，但不写数据库。受限 extract、私有映射、manifest
和 receipt 只写入 UCSF `output_root`，不进入 Git。它不是 cohort，也不证明样本代表性。

`plan` 只读配置，不访问数据、不创建输出，并显示三来源最坏情况下的注册键预算。
新示例每源 3,000 行，最多 9,000 个注册键，可容纳于 10,000 的共享额度；现有私有
配置不自动修改。预算匹配不等于覆盖一致。现有执行入口须经 Slurm，受文件、目录、行、键、
CPU、内存与运行时间上限约束。达到扫描上限时输出 `limited`，不能把未扫描到的
给药当作没有给药，也不能据此确认单次执行。报告留在 UCSF 仓库外。

## 实现状态

| 能力 | 状态 |
| --- | --- |
| 合成轨迹、内部事件 schema、时间及关联校验 | 已实现 |
| 24h 输入窗、可用时间过滤、患者级划分 | 已实现 |
| 分段指数竞争风险基线、CIF、删失似然 | 已实现 |
| 患者簇 bootstrap CI、可复现实验清单 | 已实现 |
| Git 交接提示词、发布前检查、CI | 已实现 |
| 有界 metadata-only 审计、CPU Slurm 提交工具 | 已实现；CPU Slurm 已用于可行性任务 |
| 配置驱动的三来源有界可行性验证、汇总计数、资源限制 | 已在 UCSF 运行；两次 limited，前缀关联取样无有效覆盖 |
| 规划注册键预算诊断 | 已实现；示例每源行上限降低，其他额度不扩大 |
| 一致来源 manifest、独立扫描／字节／保留预算、双校验和执行绑定 | 已实现；真实 coherent 作业 complete、无限额触发 |
| 单独授权的全源 coherent 准备器 | 已实现并运行；UCSF-only 投影、manifest 和 receipt 验证通过 |
| 临床 cohort 协议与 data-free readiness gate | 已实现；私有协议已冻结，限定候选域内 readiness 门槛通过 |
| 精确键索引／探查后端 | 能力复核未发现可用服务；未实现，也不隐藏全源扫描 |
| UCSF 有界 cohort、患者划分、首次执行／竞争事件／删失标签 | 已实现并完成真实提取；候选数上限饱和，不代表总体完整性 |
| 无特征／固定年龄分组 CPU 基线 | 已完成服务器验证；仅为管线控制，测试集未评估 |
| 双时钟历史与固定八维 CPU 比较 | 已完成；E003 推进门槛未通过，真实产物仅在 UCSF |
| 合成时间配对机制诊断 | 已实现；三种情形、共同时间尺度及同维度对照，本地生成数据验证 |
| 合成配对压力检查与额外时间尺度对照 | 已实现；S002，报告绝对及相对退化，不触发临床推进 |
| 训练历史时间变化只读审计 | UCSF job 39325 完成；现有保留训练历史不支持配对对照，私有报告不入库 |
| 固定数据的单时钟工作流开发实验 | W001 已实现并通过生成验证；原训练患者内五折 CV，真实运行待执行 |
| LightGBM、Transformer、点过程、结构化神经模型 | 未实现；E003 后未安排神经模型推进 |
| 生理状态预测、IPCW 校准／判别 | 未实现；原生理状态方向停止 |
| GPU／多卡训练 | 未实现；入口会明确拒绝提交 |

核心研究文件：[假设](docs/03_research_questions.md)、
[实验设计](docs/11_experiment_design.md)、[研究日志](docs/20_research_log.md)、
[首轮 Mac 开发交接](docs/21_mac_development_handoff.md)、
[服务器发现的契约缺口](docs/23_feasibility_contract_gaps.md)、
[首次 v2 有界运行发现](docs/24_bounded_run_findings.md)、
[关联访问设计](docs/25_coherent_access_design.md)、
[临床 cohort 协议 gate](docs/26_clinical_cohort_protocol.md)。
依赖默认保持轻量；DuckDB/LightGBM/scikit-learn 在 `research` extra，
PyTorch 在 `neural` extra，Phase 0 不安装这些大模型依赖。

本项目研究预测关系，不声称识别治疗的因果效应。合成数据的生成机制、药物类别和
检验数值都是虚构的，不能解释为临床证据。
