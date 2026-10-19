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
没有新的临床任务、神经模型或 GPU 工作排期。本地路径修复及合成检查不需要重跑这些
任务。最新状态见 docs/20，模型与实验局限见 docs/08、docs/11。

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

## 下一次真正需要 UCSF 数据的步骤

2026-10-19：`clock-audit` 已通过生成数据及模拟调度器测试，尚未在 UCSF 运行。
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
不触发新模型训练。下一项研究设计须结合这些真实事实再确定。
