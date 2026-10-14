# Local Git → UCSF pull → server Codex

用户已明确采用 Git 交接。Mac 端不配置到 UCSF 的 SSH/rsync，不拉取数据或日志。
远程仓库尚未建立；等用户提供地址后才配置 origin。

## 本地发布

```bash
make setup
make check
make demo
git add README.md AGENTS.md Makefile pyproject.toml uv.lock .python-version .gitignore .env.example src tests scripts slurm configs docs fixtures results/README.md .github
git commit -m "Describe the verified code change"
make handoff
# 用户给出地址后：git remote add origin <USER_SUPPLIED_URL>
scripts/publish.sh
```

脚本要求工作区干净、检查通过，使用普通 push。交接提示词在被忽略的
`handoff/UCSF_CODEX_PROMPT.md`，含完整提交 SHA。不要把待审核的服务器结果混进提交。
每次更新代码后重新生成提示词，防止用新代码配旧指令。

## UCSF 首次接手

用户 clone 仓库；后续用 `git pull --ff-only`，保留服务器未提交工作。
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
提交工具只支持 schema-audit 或 synthetic，小于 30 分钟、至多 4 CPU、16 GiB，
不请求 GPU。`plan` 不创建目录、不提交任务、不访问数据行。

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
