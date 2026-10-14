# Intent–Execution–State Modeling

本地 Mac 开发与合成数据验证 → Git push → 用户在 UCSF pull → 服务器端 Codex
接手临床数据工作。**本地不通过 SSH 访问 UCSF，不传回患者级数据。**

Phase 0 已提供可执行研究基础设施。它不证明结构化模型优于普通时序模型，
也不包含已经验证的 UCSF 字段映射或临床训练结果。

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

## 两端 Codex 交接

1. 本地运行 `make check` 和 `make demo`，更新研究日志，提交代码。
2. `make handoff` 生成 `handoff/UCSF_CODEX_PROMPT.md`，固定当前干净提交的完整 SHA。
3. 用户提供远程仓库地址后配置 `origin`，运行 `scripts/publish.sh`。脚本核验、测试后
   执行普通 push，不创建远程仓库、不强推。
4. 用户在 UCSF 首次 clone 或后续 `git pull --ff-only`，将交接提示词给服务器端 Codex。
5. 服务器 Codex 核验 SHA、阅读 `AGENTS.md`，先运行合成验证，再核实本地权限及
   服务器配置。首次真实数据任务仅进行有界的 Parquet footer 审计。

提示词模板见 [docs/server_codex_prompt.md](docs/server_codex_prompt.md)，
操作细节见 [docs/16_remote_development.md](docs/16_remote_development.md)。
Git 仓库只承载代码、文档、合成测试及空白配置；schema 报告和真实结果留在服务器。

## 实现状态

| 能力 | 状态 |
| --- | --- |
| 合成轨迹、内部事件 schema、时间及关联校验 | 已实现 |
| 24h 输入窗、可用时间过滤、患者级划分 | 已实现 |
| 分段指数竞争风险基线、CIF、删失似然 | 已实现 |
| 患者簇 bootstrap CI、可复现实验清单 | 已实现 |
| Git 交接提示词、发布前检查、CI | 已实现 |
| 有界 metadata-only 审计、CPU Slurm 提交工具 | 已实现；未在 UCSF 验证 |
| UCSF/MIMIC 适配、真实 cohort、临床语义映射 | 未实现，需先审计 |
| LightGBM、Transformer、点过程、结构化神经模型 | 后续研究阶段 |
| 状态预测、IPCW 校准／判别、多模型统计比较 | 后续研究阶段 |
| GPU／多卡训练 | 未实现；入口会明确拒绝提交 |

核心研究文件：[假设](docs/03_research_questions.md)、
[实验设计](docs/11_experiment_design.md)、[研究日志](docs/20_research_log.md)。
依赖默认保持轻量；DuckDB/LightGBM/scikit-learn 在 `research` extra，
PyTorch 在 `neural` extra，Phase 0 不安装这些大模型依赖。

本项目研究预测关系，不声称识别治疗的因果效应。合成数据的生成机制、药物类别和
检验数值都是虚构的，不能解释为临床证据。
