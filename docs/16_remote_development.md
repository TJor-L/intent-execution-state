# Mac 主开发，UCSF 真实验证，Git 按里程碑同步

2026-10-16 用户将主要开发工作移回 Mac。Mac 负责通用代码、生成数据的测试、研究审查
和可复现的命令准备。UCSF 保留真实输入、私有配置、临床产物和真实验证；用户可直接
提交 Slurm 脚本，不需要服务器 Codex 参与每一次运行。同一分支当前由 Mac 主要写入。

Git 只承载通用代码、合成测试、空白配置和审核后的操作摘要。远程仓库为
`https://github.com/TJor-L/intent-execution-state.git`。Mac 不连接 UCSF SSH/rsync，
不拉取临床数据、schema、日志、预测或模型。移动开发地点不改变数据边界。

## 当前里程碑

服务器已完成 coherent 准备／验证、有界 cohort、基础及年龄基线、完整来源扫描后的
双时钟历史和固定特征 CPU 比较。E003 未通过收益与不确定性门槛，测试集保持封存；
R001 job `39335` 已在 `2176207` 完成，主要比较为未确定／较差／相同，按协议收尾。
当前没有待运行的服务器任务、神经模型或 GPU 排期。
不需要重跑先前已完成的任务。最新状态见 docs/20，模型与实验局限见 docs/08、docs/11。


## R001 已完成：结果与运行记录存档

用户回传固定版本 `21762073fe9aff38dfb37d9feddc54e9205fe1fa` 的 job `39335` 已完成，
监控器已验证产物；关联原 W001 job `39332` / `9fcdc32`。原训练患者内三种子嵌套 CV
完成，原验证／测试保持封存，无源扫描／GPU。Mac 未访问 UCSF 或下载私有产物。

新选择规则减去整体损失选择规则的主要误差范围，在种子 20261020 包含零、20261021
高于零、20261022 两种规则预测完全相同。按医嘱加权的方向一致。前两个种子的逐时点
方向互换，不能挑其中有利者作为新主结果。完整定性结论见 docs/11、docs/20。

固定研究已完成，没有新的服务器命令需要运行。不要重复提交、调参、扩充候选模型、
重校准或开启原测试以寻找正结果。`private_review_required` 不表示作业失败或需要
服务器 Codex 批准；`publication_readiness: not_established` 也不是失败状态。

已有私有输出目录含 `selection_report.json`、`models.json`、`config.json`、
`paper_tables.md` 和带校验和的 `manifest.json`。数值表、模型、患者集合 hash 和日志
继续留在 UCSF；论文数值整理可复用这些产物，不需要再拟合。Mac 仅维护已获准的定性
研究记录和论文草稿，不请求下载这些文件。

以下命令是已完成作业的入口记录，不是当前操作指令；它曾在固定 `2176207` checkout
中执行。今后源码里的入口保留用于复现，不构成重跑或追加实验授权。

```bash
# Historical invocation only — job 39335 is complete; do not resubmit.
bash scripts/run_selection.sh 39332 9fcdc32f3200931c780e0931130a3a07fc20ddaa
```

脚本复用了原仓库配置和已有 Python，自动完成 preflight、plan、submit、wait，绑定
原 W001 的 job/SHA 与 cohort/history manifest。原模型不是选择输入。固定预算为
2 CPU／4 GiB／1200 秒，8 候选、480 拟合；详细协议保持在 docs/11。

## 本地循环

复用已安装环境；只有依赖或环境改变时才需要 `make setup`。

```bash
# 编辑期间运行相关测试
uv run --locked pytest tests/test_clinical_baseline.py tests/test_clinical_history_models.py tests/test_history_piecewise.py

# pipeline 改动完成后
make check
make demo
```

`make demo` 只使用生成的数据，其结果不代表临床表现。测试里的私有产物接口通过
进程内替换授权根目录来读取生成的夹具；没有开放用于本地读取临床数据的 CLI 开关。
普通实现和测试无需交接服务器。检查失败应修复并记录，不跳过检查发布。

## 有具体真实验证任务时

先完成独立可做的代码、合成测试和命令准备。每项任务明确目的、实际代码 SHA、私有
输入的版本／校验和、资源范围、预期产物及验收标准。服务器私有路径只在服务器填写。
复用已有审核映射、协议、来源和环境，不自动重建或覆盖它们。

只有用户明确要求时才 commit/push；若正式任务需要新干净提交，说明这个具体需要。
获得提交／发布指令后，审阅 diff、仅暂存通用源码和获准文档，使用普通 push；
`scripts/publish.sh` 会运行检查并生成绑定干净提交的提示词。不要强推。

用户在 UCSF 的开发 checkout 中先检查工作区，再按需要执行：

```bash
git status --short
git pull --ff-only origin main
```

有未提交改动或分支分歧时先整合，不 reset、不覆盖。排队／运行任务使用的 checkout
不能 pull 或编辑。真实任务使用独立、干净且固定提交的 job checkout，并绑定现有
私有配置；Python 环境也须指向该版本，不能让 editable install 意外指向别的开发副本。

服务器操作保持 `scripts/server.py preflight / plan / submit` 与相应 Slurm 入口。
`plan` 不扫描临床源数据；它可能读取私有配置、manifest 及计算校验和。已有命令支持
schema-audit、synthetic、feasibility、coherent-prepare、cohort-vocabulary、
cohort-eligibility、cohort-extract、clinical-baseline、clinical-features、
clinical-age-baseline、dual-clock-history 和 clinical-history-models。每种入口有各自的
审核条件和预算；工具存在不代表需要重新运行。当前不提供默认临床重跑命令。

在服务器通过 squeue/sacct 监控到终态，并在当地核验 manifest、校验和、覆盖及输出。
进程退出不等于研究门槛通过；limited 不等于完整证据，无报告也不等于零事件。
普通代码缺陷可用合成最小复现交回本地；只传递审核过的状态与错误类别，不粘贴
私有堆栈、记录、真实字段、指标、路径或原始日志。

## 研究与运行边界

E003 的既有负结果保留。不能调整其门槛追求通过，也不能把已经使用的验证集当成
新的确认性证据。新的研究设计需说明信息、对照、预算及验证复用问题；继续封存测试集。
新增来源、持久化索引／提取、全源扫描或超出已审核预算的运行，须先明确范围与成本，
不能隐藏在小规模 probe 中。获准范围内的普通修复不需要逐步交接。

里程碑摘要应包含基准 SHA／是否有未提交改动、实际检查、真实任务状态、覆盖限制
和下一步。检查通过不自动触发提交、发布、临床重跑或数据传输。

## A001 已完成：保留的运行流程与后续边界

2026-10-19：用户回传提交 `14b8d69` 上的 UCSF job `39325` 已完成，监控器返回
`status: complete`、`private_review_required: true`，已通过产物校验。随后用户反馈的
定性结论不支持现有保留训练历史上的配对对照；当前不安排继任模型，也不重复审计。
报告、具体计数和映射证据不入库。下面保留首次运行步骤供参考，不是新的运行指令。
它复用既有 cohort/history，检查训练历史是否支持时间配对问题，不拟合模型。
仅投影 cohort 的患者／医嘱身份及 split 元数据以核验患者隔离；历史时间只聚合训练
订单。不投影 duration/cause/outcome，不评估验证集或测试集，不保存任何行。
摘要计算和共享 Parquet 页可能触及其他分区字节，不等于解码或统计其结局或特征。

固定资源：2 CPU、4,096 MiB、worker wall/CPU 各 300 秒，Slurm 5 分 30 秒。
上限为 20,000 cohort 行、500,000 history 行；每个 Parquet 最多 256 MiB，footer
声明的未压缩 row-group 总字节每文件最多 512 MiB。只使用两份既有受限产物及其
QC/manifest，不扫描原始数据根、不创建索引／提取，不自动扩大配额。

`--auto-artifacts` 只查看 `output_root/jobs` 的最多 1,000 个直接子项及固定的
`cohort-extract` / `dual-clock-history` 子目录，读取 manifest 总量不超过 16 MiB。
必须有唯一一对按 cohort-manifest 摘要绑定的 complete 产物。多个候选、没有匹配、
符号链接或超限均明确停止，不按最新目录猜测。需要时仅在服务器用 `--cohort-dir`
及 `--history-dir` 明确指定已有审核产物，代替自动发现；路径不回传 Mac。

新代码发布后，在 UCSF 原有项目目录执行。创建独立 job checkout，保留现有源码
和私有配置，复用原 Python 环境。若不用 uv，直接将 `IES_JOB_PYTHON` 设为既有环境
的 Python 绝对路径，不重装环境。

```bash
(
set -euo pipefail
cd "$(git rev-parse --git-common-dir)/.."
IES_REMOTE_CONFIG="$PWD/configs/remote.local.yaml"
IES_UV="$(command -v uv || printf '%s' "$PWD/.tools/bin/uv")"
IES_JOB_PYTHON="$("$IES_UV" run --locked --no-sync python -c 'import sys; print(sys.executable)')"
git fetch origin main
IES_JOB_CHECKOUT="$PWD/handoff/clock-audit-$(git rev-parse --short origin/main)"
git worktree add --detach "$IES_JOB_CHECKOUT" origin/main
cd "$IES_JOB_CHECKOUT"
export IES_EXECUTION_CONTEXT=ucsf

PYTHONPATH="$PWD/src" "$IES_JOB_PYTHON" scripts/server.py plan clock-audit \
  --config "$IES_REMOTE_CONFIG" --auto-artifacts
PYTHONPATH="$PWD/src" "$IES_JOB_PYTHON" scripts/server.py submit clock-audit \
  --config "$IES_REMOTE_CONFIG" --auto-artifacts --wait
)
```

核对 plan 的固定范围后提交。worktree 目录存在时拒绝覆盖，先确认原作业状态；不要
删除或修改可能正在使用的 checkout。排队／运行期间不编辑代码、输入或共享 Python
环境。Slurm 强制加载 job checkout 的 `src`，避免 editable install 指向旧代码。

工具先写入私有 submission receipt，再用 `sacct` 监控精确 job ID，忽略 batch/extern
子步骤。监控预算一小时，每 15 秒查询；超时、查询错误或 Ctrl-C 不会取消或重提。
按已经输出的 job ID 在服务器查 squeue/sacct，不重复 submit。成功需核验 manifest
及报告摘要；终端只输出 job ID／运行状态，不输出计数、路径、原始错误或审计结论。

私有报告在该 job 的 `clock-audit/clock_report.json`，可通过私有 `submission.json`
定位。当地需核实：各类型是否有非零记录延迟；同类型事件是否存在不同的时间对且
允许有效的边缘分布保持交换；无历史和达到保留上限的情况。原始计数／报告留在 UCSF。
交接只返回当地审核批准的操作结论，不粘贴报告、真实值、字段或日志。

零交换计数只针对保留历史中的这个对照；正计数不说明样本充分、模型有益或时间语义
获得新验证。相同时钟需要额外单时钟尺度对照。此审计不恢复 E003，不开启测试集，
不触发新模型训练。现有结果已排除在这份保留历史上直接推进当前配对对照；下一项
独立问题及已有验证集的使用方式须先定义，不能靠调整映射或保留上限绕过这一结论。

## 当前任务 W001：固定数据的单时钟工作流开发实验

用户已回传 `9fcdc32` 上的 job `39332` 完成且产物校验通过。类型特异时间未通过固定
支持条件且平均损失高于合并时间；简单数量和合并时间对照的平均方向较好，条件区间
与折间方向待只读核验。以下提交命令保留作记录，不要再次提交已完成任务。

用户已授权换方向，且明确无法增加／修改数据或获得进一步解释。W001 完全复用已有
cohort/history 的审核语义与覆盖，不更改来源、映射、窗口、保留上限或原始患者划分。
首次执行、其他终止原因与右删失沿用原标签。历史数量、合并类型的时间分布、区分类型
的时间分布与无特征模型逐层比较，不能把历史数量差称为待执行医嘱数量。

本轮只使用原训练患者做五折 CV；原验证／测试结局和历史特征不参与分析。它是数据
反馈后的探索性开发实验，不是新的独立确认。固定设计和发展支持规则见 docs/11。
不要求人工补充字段解释，不自动打开测试集或触发 GPU，也不因为负结果改阈值。

范围：最多 20,000 cohort 行、500,000 history 行；每份 Parquet 最多 256 MiB、声明
的未压缩 row-group 字节最多 512 MiB。发现已有输入沿用 A001 的目录／manifest 限额。
模型资源沿用既有临床 CPU 模型预算：2 CPU、4,096 MiB，worker wall/CPU 各 1,200 秒，
Slurm 20 分 30 秒。新任务最多拟合四模型乘五折，不进行超参数搜索或自动扩大资源。
所有权重和聚合指标留在 UCSF；不保存逐订单预测文件，不向终端输出真实统计量。

代码发布后，在仓库任一 checkout 内运行以下命令；它先定位原项目目录，再创建新的
独立 job checkout。将 `IES_JOB_COMMIT` 替换为本次交付的完整 SHA。

```bash
(
set -euo pipefail
cd "$(git rev-parse --git-common-dir)/.."
IES_REMOTE_CONFIG="$PWD/configs/remote.local.yaml"
IES_UV="$(command -v uv || printf '%s' "$PWD/.tools/bin/uv")"
IES_JOB_PYTHON="$("$IES_UV" run --locked --no-sync python -c 'import sys; print(sys.executable)')"
IES_JOB_COMMIT="REPLACE_WITH_DELIVERED_COMMIT"
git fetch origin main
IES_JOB_CHECKOUT="$PWD/handoff/workflow-cv-${IES_JOB_COMMIT:0:7}"
git worktree add --detach "$IES_JOB_CHECKOUT" "$IES_JOB_COMMIT"
cd "$IES_JOB_CHECKOUT"
export IES_EXECUTION_CONTEXT=ucsf
export PYTHONPATH="$PWD/src"

"$IES_JOB_PYTHON" scripts/server.py preflight --config "$IES_REMOTE_CONFIG"
"$IES_JOB_PYTHON" scripts/server.py plan workflow-cv \
  --config "$IES_REMOTE_CONFIG" --auto-artifacts
"$IES_JOB_PYTHON" scripts/server.py submit workflow-cv \
  --config "$IES_REMOTE_CONFIG" --auto-artifacts --wait
)
```

发现不唯一时，仅在 UCSF 显式指定既有 `--cohort-dir` 和 `--history-dir`，不要猜测
最新目录。已经输出 job ID 时按该 ID 查作业；监控中断或超时不重提、不自动取消。
监控成功需检查 clean commit、manifest、报告、模型及配置摘要，不能只看进程退出。

本次私有产物是作业目录下 `workflow-cv/workflow_report.json`、`models.json`、
`config.json` 和 `manifest.json`。反馈先提供 job ID、运行状态与固定错误类别。研究
反馈仅限当地允许共享的定性结论，特别是固定的 `typed_timing_development_support`
是否满足；原始损失值、区间、计数、权重、路径、报告和日志均留在 UCSF。
支持标志仅决定是否值得设计下一轮验证，不代表已证明临床价值或论文贡献。失败或
未获支持均保留，由 Mac 做生成复现和代码诊断，不依赖服务器编码 agent。

### 已完成 job 39332 的只读核验

首次长段内联命令的定性反馈已收到。现改用经过生成测试的短入口，核验原有报告中的
条件区间和折间方向。只读既有 receipt、manifest、报告和配置，并核验模型文件摘要；
不解码模型权重、不读临床行、不拟合、不重采样、不提交作业、不修改临床产物。
最多查看 1,000 个直接 job 目录，每份 receipt 最多 16 KiB；报告与配置各最多 1 MiB，
模型摘要检查最多 64 MiB。必须恰好匹配指定 job ID、原作业提交和完整产物。

在仓库任一 checkout 内运行以下步骤。把 `IES_REVIEW_COMMIT` 替换为本次交付的
完整审阅工具 SHA；原作业版本仍固定为 `9fcdc32`，不修改它的 checkout。

```bash
(
set -euo pipefail
cd "$(git rev-parse --git-common-dir)/.."
git fetch origin main
IES_REVIEW_COMMIT="REPLACE_WITH_DELIVERED_REVIEW_COMMIT"
IES_REVIEW_DIR="handoff/workflow-review-${IES_REVIEW_COMMIT:0:7}"
git worktree add --detach "$IES_REVIEW_DIR" "$IES_REVIEW_COMMIT"
bash "$IES_REVIEW_DIR/scripts/review_workflow.sh" 39332 9fcdc32f3200931c780e0931130a3a07fc20ddaa
)
```

包装脚本复用原项目的 `configs/remote.local.yaml` 和已有 Python 环境（`uv --no-sync`），
进入新的干净审阅 checkout，再执行：

```bash
python scripts/server.py review workflow-cv --config /SERVER_ONLY/remote.local.yaml --job-id 39332 --source-commit 9fcdc32f3200931c780e0931130a3a07fc20ddaa
```

输出只包含固定 job/source/reviewer 绑定、完整性状态、既有支持标志及四个预设比较：

- `mean_loss_direction`: `lower` / `higher` / `equal`，仅代表平均损失方向。
- `conditional_interval`: `below_zero` / `above_zero` / `includes_zero`；触及零也归入包含零。
- `fold_directions`: `all_lower` / `all_higher` / `all_equal` / `mixed`。

这些是已有探索性结果的定性描述，没有新设次要比较的通过规则。条件区间不含重拟合、
折间训练依赖和设计选择的不确定性；方向也不说明改善幅度或临床效用。按当地共享规则
反馈定性结论即可，完整指标、计数、报告、日志、私有路径和权重留在 UCSF。

### W001/W002 已完成；以下诊断步骤存档，不重复执行

用户已回传 `5836dbc` 的完整定性核验：合并时间相对数量、类型特异时间相对无特征
的条件区间低于零、五折均较低；数量相对无特征、类型特异时间相对合并时间的区间
包含零、折间方向混合。无需重复只读审阅或重提 W001。主假设仍未获支持。

用户已回传 W002 job `39333` 在 `1df3274` 上完成，并收到自动核验后的定性摘要。
W001/W002/R001 均没有待提交任务；最新完成状态见文首。不重复旧作业、不打开原验证／测试或挑有利时点。
完整研究结论见 docs/11、docs/20。

W002 只重放 job `39332` 已保存的模型。它先复现原五折损失，再直接补充合并
时间与无特征的对比，并诊断 1/4/12/24 小时首次执行概率。提前删失保留为未知结局；
误差范围与描述性校准均是探索性结果，没有新通过规则，也不用于重训／调参。
原验证和测试结局／特征不参与。不会重新扫描原始来源或写预测行。

2 CPU、4,096 MiB；worker 300 秒，Slurm 上限 5 分 30 秒。复用原配置和依赖环境，
不扩容、不用 GPU。下面保留已完成任务的原始步骤以便追溯，不作为下一项操作。
它只新增独立代码 worktree 和私有 aggregate 诊断产物，原模型与旧 checkout 不改动。

```bash
(
set -euo pipefail
cd "$(git rev-parse --git-common-dir)/.."
git fetch origin main
IES_DIAGNOSTIC_COMMIT="1df32744dcbcd2aebaa89174fee1de546f4ddd2a"
IES_DIAGNOSTIC_DIR="handoff/workflow-diagnostics-${IES_DIAGNOSTIC_COMMIT:0:7}"
git worktree add --detach "$IES_DIAGNOSTIC_DIR" "$IES_DIAGNOSTIC_COMMIT"
bash "$IES_DIAGNOSTIC_DIR/scripts/diagnose_workflow.sh" 39332 9fcdc32f3200931c780e0931130a3a07fc20ddaa
)
```

脚本自动 preflight → plan → submit → wait。指定的原 job receipt 必须唯一，模型
manifest 必须绑定原 SHA、发现的 cohort/history 和未改动的 W001 配置。不满足则停止，
不会猜路径、选最新模型或重训。监控最多等待一小时；到时不会取消／重新提交作业。
失败后只反馈固定错误类别与 job ID，不自动重跑，不粘贴日志。

完成后最后一个 JSON 自带 `diagnostics`，不再需要另贴 Python 来读取报告：

- `nll_comparisons`：五项平均方向、条件区间位置和折间方向。新增的
  `pooled_minus_intercept` 明确属于事后描述性比较。
- `paired_brier_completion_bounds`：每个固定时点，配对概率误差的可能范围相对零的
  位置。`below_zero` 表示在当前样本允许的二元结局补全下均较低；不是置信区间或显著性结论。
- `empirical_mean_risk_vs_outcome_bounds`：平均预测概率在当前样本结局比例范围的
  `below`／`inside`／`above`。`inside` 不是校准通过，`outside` 也不是总体失准的统计证明。

最后的定性 JSON 已回传，足够完成本轮审查；不需要继续抄取报告或运行服务器命令。
完整 `diagnostic_report.json`、计数、指标、分箱、日志、模型与私有路径留在 UCSF。
合并时间模型的整体损失较低，但执行概率相对数量模型在 4/12/24 小时较差；所有模型
平均概率在 1 小时低于样本结局范围、4 小时高于范围。结果不支持全面改进或校准通过。
现有数据范围以外的泛化、改善幅度与临床效用仍未验证。
