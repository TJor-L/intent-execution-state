# UCSF 服务器端 Codex 交接提示词

请在 UCSF 授权服务器上的 `intent-execution-state` 仓库内执行下面的工作。
你是服务器端 agent；本地 Mac 端 agent 已完成 Phase 0 合成基础设施。

本次预期 Git 提交：`{{COMMIT_SHA}}`

## 1. 核验接手版本

- 先阅读 `AGENTS.md`、`README.md`、`docs/05_data_schema.md`、
  `docs/15_privacy_security.md` 和 `docs/16_remote_development.md`。
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

## 3. 首次真实数据任务：有界的元数据审计

当前授权范围是 Phase 0 有界 footer 审计，不是全表扫描、cohort 提取或训练。

```bash
uv run python scripts/server.py plan schema-audit
uv run python scripts/server.py submit schema-audit
```

默认最多读取 12 个 Parquet 文件的 footer、遍历 100 个目录；没有数据行扫描。
如果首轮数据目录不具代表性，先定位目标表目录，再逐个执行小范围审计。
不要把整个 1.4 TiB 数据集当作默认审计对象。不要自动扩大配额。
用服务器端 `squeue`/`sacct` 核实 job 状态；本地 agent 无法替你核实。
任务排队和运行期间不要在同一 checkout 中 pull 或修改源码；需要继续开发时使用
独立 checkout。任务启动会核验提交 SHA，但不会为运行中的代码创建快照。

优先核实候选 medicationorderfact、medicationadministrationfact、
labcomponentresultfact、hospitaladmissionfact、encounterfact 是否存在。
这些名称来自研究记录，尚未由实际 schema 确认。
将具体字段、schema 报告、路径、日志和任何数据值全部保留在 UCSF。
Footer 只能确认字段类型，不能确认状态码、时间含义或关联质量；不要据此编造语义。

## 4. 输出本次交接结果

在服务器受限输出目录生成交接报告，包含：实际 SHA、环境检查、Slurm job 状态、
审计覆盖范围／是否截断、需要人工确认的语义、下一步最小可行任务。
不要将患者级数据、示例记录、患者标识、真实值、未审核 schema、日志、权重、
私有路径或密钥推送回 Git，也不要粘贴到 Mac 端对话。

用户可带回的默认简短状态：

```text
代码 SHA：<已核对/不一致>
合成测试：<通过/失败及不含数据的原因>
元数据任务：<未提交/排队/完成/失败>
候选表及关键字段验证：<完成/部分/待验证，不附原始 schema>
下一步：<代码需求或需要人工确认的语义，不含记录和路径>
```

若需向本地交接适配器开发需求，先由用户核准可分享的脱敏逻辑字段映射。
尚未实现的真实数据适配器必须保持显式缺失；不得偷偷用合成数据替代真实实验。
此轮不使用 GPU、不下载 MIMIC、不进行临床模型训练，也不宣称治疗因果效应。
