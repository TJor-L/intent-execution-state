# Intent–Execution–State Modeling

**UCSF 负责主要开发与测试，Mac 负责方案讨论和代码复核。** 服务器连续完成实现、
合成测试、小规模真实验证和修复，按里程碑通过 Git 同步，不逐步往返交接。
本地不通过 SSH 访问 UCSF，不传回患者级数据。

Phase 0 已提供可执行研究基础设施，并加入服务器交接要求的有界可行性验证器。
它不证明结构化模型优于普通时序模型，也不包含真实 UCSF 字段映射或临床训练结果。

## 本地快速开始

需要 Python 3.11+ 和 uv。此工作区已安装项目内 uv；Makefile 自动发现它。
新机器可按 [uv 官方说明](https://docs.astral.sh/uv/getting-started/installation/)
安装，或运行 `python3 -m pip install --target .tools uv`，无需更改系统 Python。

```bash
make setup        # uv sync --locked，安装锁定依赖及项目环境
make check        # Ruff、测试、Git 文件边界检查
make demo         # 新建独立运行目录，生成 → 校验 → cohort → 训练 → 评估
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

独立步骤（输出路径必须尚不存在）：

```bash
uv run python scripts/generate_synthetic.py
uv run python scripts/validate_schema.py
uv run ies build-cohort --events artifacts/synthetic/events.parquet --output artifacts/synthetic/cohort.json
uv run ies train --cohort artifacts/synthetic/cohort.json --output artifacts/synthetic/model.json
uv run ies evaluate --cohort artifacts/synthetic/cohort.json --model artifacts/synthetic/model.json --output-dir artifacts/synthetic/evaluation
```

## 两端 Codex 分工

1. 用户在 UCSF 拉取最新代码，把生成的提示词交给服务器 agent；初始 SHA 用于接手核验。
2. 服务器直接核实访问能力、实现读取器、补合成测试，并在已审核范围内运行 CPU 验证。
   发现普通代码、配置或调度问题就地修复，不等待 Mac 实现下一步。
3. 编辑时运行针对性测试；pipeline 变更完成后运行 `make check`、`make demo` 并提交。
   真实任务绑定实际干净提交；运行中的源码/配置不能修改，开发使用独立 checkout。
4. 里程碑完成后更新研究日志，使用 `scripts/publish.sh` 普通推送；脚本检查并生成
   固定当前提交的 `handoff/UCSF_CODEX_PROMPT.md`。无需每次小提交都要求用户来回同步。
5. Mac 拉取里程碑代码进行复核和讨论。只有确实缺少访问/语义/能力或需要扩大工作范围，
   才返回具体阻碍；同一分支避免双端同时改动。

提示词模板见 [docs/server_codex_prompt.md](docs/server_codex_prompt.md)，
操作细节见 [docs/16_remote_development.md](docs/16_remote_development.md)。
Git 仓库只承载代码、文档、合成测试及空白配置；schema 报告和真实结果留在服务器。

## 本轮更新：取样发现、预算诊断与关联读取设计

服务器的两次小规模任务产出了有效 `limited` 报告，但独立来源前缀之间没有相同
身份覆盖；这不能证明缺少真实关联。下一步需先审核已有一致来源或精确键探查能力。
详见[服务器发现](docs/24_bounded_run_findings.md)与[下一阶段接口设计](docs/25_coherent_access_design.md)。
服务器能力复核未发现保留精确医嘱—给药及 encounter 身份的现成索引；现有患者分片
MEDS 产物不能满足该验证器。现已实现 `coherent_manifest` 后端：它只读取经审核 manifest
中列出的 Parquet 文件和 row group，并分别限制扫描行、row-group 字节、保留行和 seed 键。
真实运行仍须先有一个绑定当前私有映射与不可变快照、且证明三来源覆盖完整的服务器本地
manifest；当前没有该 manifest，不能伪造或用隐藏全表扫描生成。原先“仅审核后返回 Mac”
的安排已取消，也不重复没有变化的前缀扫描。

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
| 一致来源 manifest、独立扫描／字节／保留预算、双校验和执行绑定 | 已实现并通过合成测试；尚无经审核的真实私有 manifest |
| 精确键索引／探查后端 | 能力复核未发现可用服务；未实现，也不隐藏全源扫描 |
| UCSF/MIMIC cohort 适配、真实 cohort、临床语义映射 | 未实现；真实映射仅在服务器本地审核 |
| LightGBM、Transformer、点过程、结构化神经模型 | 后续研究阶段 |
| 状态预测、IPCW 校准／判别、多模型统计比较 | 后续研究阶段 |
| GPU／多卡训练 | 未实现；入口会明确拒绝提交 |

核心研究文件：[假设](docs/03_research_questions.md)、
[实验设计](docs/11_experiment_design.md)、[研究日志](docs/20_research_log.md)、
[首轮 Mac 开发交接](docs/21_mac_development_handoff.md)、
[服务器发现的契约缺口](docs/23_feasibility_contract_gaps.md)、
[首次 v2 有界运行发现](docs/24_bounded_run_findings.md)、
[关联访问设计](docs/25_coherent_access_design.md)。
依赖默认保持轻量；DuckDB/LightGBM/scikit-learn 在 `research` extra，
PyTorch 在 `neural` extra，Phase 0 不安装这些大模型依赖。

本项目研究预测关系，不声称识别治疗的因果效应。合成数据的生成机制、药物类别和
检验数值都是虚构的，不能解释为临床证据。
