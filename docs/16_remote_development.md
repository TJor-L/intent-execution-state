# Local Git → UCSF pull → server Codex

用户已明确采用 Git 交接。Mac 端不配置到 UCSF 的 SSH/rsync，不拉取数据或日志。
远程仓库为 `https://github.com/TJor-L/intent-execution-state.git`，本地已配置为 origin。

## 本地发布

```bash
make setup
make check
make demo
git add README.md AGENTS.md Makefile pyproject.toml uv.lock .python-version .gitignore .env.example src tests scripts slurm configs docs fixtures results/README.md .github
git commit -m "Describe the verified code change"
make handoff
scripts/publish.sh
```

脚本要求工作区干净、检查通过，使用普通 push。交接提示词在被忽略的
`handoff/UCSF_CODEX_PROMPT.md`，含完整提交 SHA。不要把待审核的服务器结果混进提交。
每次更新代码后重新生成提示词，防止用新代码配旧指令。

## UCSF 首次接手

用户首次在 UCSF 的代码目录执行：

```bash
git clone https://github.com/TJor-L/intent-execution-state.git
cd intent-execution-state
```

后续在仓库内用 `git pull --ff-only`，保留服务器未提交工作。
把生成的提示词交给服务器 Codex。服务器依赖安装方式需符合实际网络/集群规则；
环境已准备时任务直接用绝对 Python 路径，Slurm 计算节点不会自动联网安装包。

```bash
make setup
make check
make demo
cp configs/remote.example.yaml configs/remote.local.yaml
# 仅在服务器填入授权路径、Python、partition/account，并核实访问权限。
export IES_EXECUTION_CONTEXT=ucsf
uv run python scripts/server.py preflight
uv run python scripts/server.py plan schema-audit
uv run python scripts/server.py submit schema-audit
```

配置示例不含真实服务器路径。必须核实 `institutional_access_confirmed` 后才能继续。
提交工具支持 schema-audit、synthetic 和 feasibility，均不请求 GPU。
`plan` 只读配置，不创建目录、不提交任务、不检查或读取数据路径。
schema-audit/synthetic 保持原 CPU 配额；feasibility 使用映射内的更严格资源上限。

## 日志与结果

服务器输出为 `output_root/jobs/<run>/`，包括调度日志、提交记录和元数据报告；
synthetic 子任务生成自己的 manifest。用服务器端 squeue/sacct 确认是否成功，
拿到 job ID 不代表完成。审计到达上限会标记覆盖有限；没有文件或读取失败返回非零。
目录遍历顺序取决于文件系统，不能将样本视为代表性抽样。

提交前要求代码工作区干净；任务启动时再次核验提交 SHA 并使用该 checkout 的源码。
不要在任务排队或运行时修改同一 checkout／执行 pull；后续开发应等任务结束或使用
另一个独立 checkout。启动检查不是运行期间的文件快照。手工提交其他 sbatch 时也须
设置 `IES_EXPECTED_COMMIT` 为审核过的 SHA，并用 `--chdir` 指向该干净仓库。

预处理与评估 sbatch 目前只接受 canonical synthetic artifacts。GPU 入口明确失败。
真实 cohort 提取必须先实现并审核 adapter。下次本地开发只接收允许分享的需求或
聚合状态；患者级结果、原始 schema 与私有路径都留在 UCSF。

## 下一轮：有界可行性验证

1. 保留已有 `remote.local.yaml`，仅在服务器复制并填写
   `configs/feasibility.example.yaml` → `configs/feasibility.local.yaml`。
2. 核实机构授权、映射、动作、观测覆盖与时间语义后，才填写相应 reviewed 标志。
   不应把随机截取的给药文件声明为覆盖全部相关给药。尚未审核的语义应保留未完成。
3. `uv run python scripts/server.py plan feasibility --mapping configs/feasibility.local.yaml`
   只检查配置并显示资源上限。它不会确认源文件或列确实存在。
4. `uv run python scripts/server.py submit feasibility --mapping configs/feasibility.local.yaml`
   提交单个 CPU 任务；启动时核验干净代码 SHA 和提交时读取的映射字节校验和。

feasibility 的 CPU、内存和时间分配来自其映射配置，覆盖 remote 配置中的对应值。
默认 1 CPU、2048 MiB、60 秒 worker wall/CPU 限额；Slurm 增加 30 秒收尾时间。
修改排队中的映射会让任务失败，不应通过关闭核验重用旧任务。
报告位于服务器 `output_root/jobs/<run>/feasibility/feasibility_report.json`。
该任务的提交记录不写入命令参数或私有路径。失败／限额退出非零，需要结合 sacct
和报告状态解释；无报告可能是调度器/系统终止，不能视作成功。

本地 Mac 只运行合成测试；Linux 资源限额的原生集成测试由 Linux CI 执行，
实际 UCSF 的 Slurm/cgroup 行为仍需服务器确认。详见 docs/22_bounded_feasibility.md。
