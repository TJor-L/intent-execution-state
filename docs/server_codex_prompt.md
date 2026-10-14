# UCSF 服务器端 Codex 交接提示词

请在 UCSF 授权服务器上的 `intent-execution-state` 仓库内执行下面的工作。
你是服务器端 agent；本地 Mac 端 agent 已按上一轮交接完成有界可行性验证器。

本次预期 Git 提交：`{{COMMIT_SHA}}`

## 1. 核验接手版本

- 先阅读 `AGENTS.md`、`README.md`、`docs/05_data_schema.md`、
  `docs/15_privacy_security.md`、`docs/16_remote_development.md`、
  `docs/21_mac_development_handoff.md` 和 `docs/22_bounded_feasibility.md`。
- 检查 `git status --short` 和 `git rev-parse HEAD`。HEAD 应与上方完整 SHA 一致。
  如果不一致或有本地改动，先说明差异；不要 reset、强制 checkout 或覆盖服务器工作。
- 用户负责首次 clone／后续 `git pull --ff-only`。不要配置新的数据传输通道。
- 检查 Python 3.11+、uv 和服务器允许的安装方式，然后执行 `make setup`、
  `make check`、`make demo`。若不能联网安装，记录准确限制，使用获准的环境。
  不要将合成结果描述为 UCSF 结果。

## 2. 确认服务器配置

- 确认当前运行位置是获准 UCSF 环境，用户具备所需数据访问权限。
- 仅在服务器创建 `configs/remote.local.yaml`，参考 example；该文件被 Git 忽略。
- 从服务器现有配置或用户信息确认 data_root、output_root、Python 路径、
  Slurm partition/account。不要猜测账号、路径、队列、GPU 配额或临床字段。
- output_root 必须是仓库外的授权存储，与原始数据目录分离。
- 权限核实后设置 `institutional_access_confirmed: true`，并在当前服务器 shell
  设置 `export IES_EXECUTION_CONTEXT=ucsf`。这只是操作保护，不是机构授权的替代。
- 执行 `uv run python scripts/server.py preflight`；若缺必要信息，列出缺项。

## 3. 本轮任务：有界可行性验证，只输出汇总计数

上一轮仅带回了已审核的操作发现：直接关联可行、重复给药常见、患者必须一致，
encounter 不能默认精确一致，检验信息可用性仍未审核。物理字段、动作和路径继续
只留在服务器；不要要求本地 agent 填写或猜测它们。

在服务器复制 `configs/feasibility.example.yaml` 为被忽略的
`configs/feasibility.local.yaml`，用已有的受限审核结果填充逻辑映射。
本轮范围是有界的行/键验证，不是全表扫描、患者级 cohort 输出或训练。

必须核实授权、映射、数据源覆盖范围、符合剂量含义的 action allowlist 后才能设置
对应 reviewed 标志。可选的 end/discontinuation 不得自动视作终止，须确认语义。
默认使用独立给药 available_at 映射；只有已有证据支持与 occurrence 相等时才使用
`occurrence_reviewed`。不得用这个选项掩盖缺失的时间语义。时间编码和观测结束同样
需要审核。任何必要语义未明确时，列出缺项并停在配置准备阶段。

保持 labs 禁用。患者不一致直接拒绝；encounter 不一致按明确策略拒绝或计数；
重复 qualifying administration 拒绝该医嘱，不能取最早一条来让 MVP 通过。

```bash
uv run python scripts/server.py plan feasibility --mapping configs/feasibility.local.yaml
uv run python scripts/server.py submit feasibility --mapping configs/feasibility.local.yaml
```

plan 不访问数据或创建输出。默认每源最多 4 文件、20 目录、5,000 行，总计最多
10,000 个身份键；1 CPU、2,048 MiB，worker wall/CPU 时间均最多 60 秒。
先保留这些小配额，不自动扩大。配置须指向覆盖语义已审核的来源；若扫描被截断，
接受 `limited` 状态，不能声称确认了单次给药或删失。不要挑任意小 shard 来消除
这个提示。运行时仅读取映射列，患者级行仅在服务器内存中存在。
用服务器端 `squeue`/`sacct` 核实 job 状态；本地 agent 无法替你核实。
任务排队和运行期间不要在同一 checkout 中 pull 或修改源码；需要继续开发时使用
独立 checkout。代码 SHA 和映射校验和都会核验；不要修改排队中的映射。
启动检查不是运行期间的源码快照。无报告／非零退出需排查，不得当作零事件。

报告在配置的仓库外输出目录 `jobs/<run>/feasibility/feasibility_report.json`。
不要将报告当成临床结果或真实 cohort；它只是 bounded feasibility infrastructure。

## 4. 输出本次交接结果

在服务器受限输出目录记录：实际 SHA、环境检查、Slurm job 状态、验证状态／是否
达到上限、关键计数的解释、尚未确认的语义与下一步最小可行代码任务。
不要将患者级数据、示例记录、患者标识、真实值、未审核 schema、日志、权重、
私有路径或密钥推送回 Git，也不要粘贴到 Mac 端对话。

用户可带回的默认简短状态：

```text
代码 SHA：<已核对/不一致>
合成测试：<通过/失败及不含数据的原因>
有界可行性任务：<未提交/排队/complete/limited/failed/无报告>
源覆盖／时间／动作映射：<已核实/部分/待核实，不附原始 schema>
重复给药与关联规则：<可继续/需重新设计，不附未审核计数>
下一步：<代码需求或需要人工确认的语义，不含记录和路径>
```

完整计数报告默认留在 UCSF；小单元格不自动获准公开。带回本地的需求应继续采用
经核准的操作摘要，不包含字段名、私有路径、状态值或患者标识。
真实 cohort 提取仍未实现；不得偷偷用合成数据替代真实实验。
此轮不使用 GPU、不下载 MIMIC、不进行临床模型训练，也不宣称治疗因果效应。
