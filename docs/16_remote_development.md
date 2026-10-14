# UCSF 主开发，本地复核，Git 按里程碑同步

用户已将开发和测试重心移到 UCSF。服务器 agent 在同一环境内完成实现、合成测试、
获准范围内的真实小规模验证、诊断和修复；Mac 负责研究讨论、代码复核和合成复现。
不再每发现一个数据访问问题就返回 Mac 等下一次代码交接。

Git 继续只承载通用代码、合成测试、空白配置和审核后的操作摘要。远程仓库为
`https://github.com/TJor-L/intent-execution-state.git`。Mac 不配置到 UCSF 的 SSH/rsync，
不拉取临床数据、日志或模型。移动开发地点不改变数据边界。

## 首次接手与版本

用户在服务器保留已有工作，然后正常拉取：

```bash
git status --short
git pull --ff-only origin main
```

有未提交改动或分支分歧时先检查并整合，不 reset、不强推、不覆盖。把最新
`handoff/UCSF_CODEX_PROMPT.md` 给服务器 agent；生成文件固定初始接手 SHA。
这个 SHA 不是永久冻结：服务器可继续开发、测试、提交，后续任务固定各自实际代码版本。

已有环境和私有配置优先复用。首次安装或依赖变动才需要 `make setup`；当前代码在
此环境尚未核验时运行 `make check`。依赖安装须符合集群规则，计算任务不自动联网
安装软件。只有配置缺失时才参考 example 创建 `.local.yaml`，不覆盖现有审核结果。

## 连续实现与验证

服务器先核实真实访问能力，然后直接选择并实现一个可用的后端。当前目标是完成
一次覆盖同一批医嘱的关联可行性验证。参考 docs/24 的取样发现和 docs/25 的接口设计；
设计审核、编码和验证可以在服务器同一轮完成，不需要等待 Mac 接力。

日常循环是：检查证据 → 实现/修复 → 针对性合成测试 → 必要的有界真实验证 → 解释
结果并修复。只有真实验证需要经过已经核实的授权、映射、覆盖和资源约束；普通代码
缺陷、测试失败、可修复的配置/调度问题由服务器直接处理，不单独交回 Mac。

```bash
# 编辑期间：只跑与当前变更相关的测试
uv run pytest tests/test_feasibility.py tests/test_feasibility_contract_v2.py

# pipeline 变更完成，准备提交/真实任务时
make check
make demo
```

`make demo` 仅为合成端到端验证。真实临床读取走受限 CPU/Slurm 入口，不能为了方便
绕过已有运行上下文和预算保护。真实任务每次重跑应对应具体修复或新证据；不重复
没有变化的前缀扫描，也不自动扩配额。环境不变时无需重复 setup，文档改动无需重跑
临床任务。发布脚本仍会执行必要的提交前检查。

## 真实任务与正在开发的源码

真实任务提交前要求干净提交；启动时核验 SHA 和映射校验和。开发可继续，但不能
修改排队/运行任务使用的同一 checkout 或配置。可使用独立的干净 job checkout，
并给任务明确的 Python、配置路径和代码版本；不能把启动时校验误认为源码快照。

已有 `configs/remote.local.yaml` 记录获准存储、Python 和 Slurm 设置。需要验证服务器
运行环境时执行：

```bash
export IES_EXECUTION_CONTEXT=ucsf
uv run python scripts/server.py preflight
uv run python scripts/server.py plan feasibility --mapping configs/feasibility.local.yaml
```

这些现有工具支持 schema-audit、synthetic 和 v2 feasibility，均为 CPU 任务。
`plan` 不读取临床源数据、不创建输出。v2 的 identity_budget 显示三来源注册键预算；
默认每源 3,000 行、共享 10,000 键。它仍是独立前缀读取器，并不实现 docs/25 的一致
来源／精确键访问。服务器应实现并测试新后端及相应入口后再用它验证，不得把新设计
的配置项直接塞进旧入口并声称已经实现。

当前小规模默认资源为 1 CPU、2,048 MiB、60 秒 worker wall/CPU 时间；Slurm 增加
30 秒收尾时间。既有已审核配置可继续使用，不自动覆盖或扩大。新增后端必须明确
文件、row group、扫描/保留行、键、索引与 I/O 等预算，遵守已确定的运行范围。

输出在仓库外授权目录；现有 v2 报告位于
`output_root/jobs/<run>/feasibility/feasibility_report.json`。在服务器监控 squeue/sacct
至终态并解释报告。limited 使用非零退出，不等于读取程序必然出错；无报告不等于零
事件。患者级数据、源 schema、私有路径和完整受限计数继续留在服务器。

## 里程碑发布与真正的阻碍

服务器拥有当前实现分支；Mac 先复核，避免两端同时写同一分支。服务器可做小提交，
但只在完成实现/验证里程碑或遇到真实外部阻碍时集中同步。无需每次 commit 都让用户
来回 pull。先检查 diff，只暂存审核过的通用源码、合成测试和可共享文档，再发布：

```bash
git diff --cached --check
git commit -m 'Describe the verified change'
bash scripts/publish.sh
```

不暂存私有配置或数据。发布脚本要求工作区干净、检查通过后普通 push，并重新生成
固定当前 SHA 的提示词。服务器发布后确认 CI。
更新 `docs/20_research_log.md` 和实际实现状态；摘要包括 SHA、测试、真实任务状态、
覆盖限制和下一步，不能把计划写成已完成。

只有缺少权限/关键语义、没有所需访问能力，或工作需要超出现有范围时，才提交具体
阻碍。若不可避免地需要新建持久化索引、一致提取、全源扫描或新增资源，先给出范围、
成本、产物位置和验收标准；这些仍是单独操作，不能隐藏在小规模 probe 内。无需因此
搁置独立可完成的代码与合成测试。当前里程碑不包含真实 cohort 导出或 GPU/临床训练。
