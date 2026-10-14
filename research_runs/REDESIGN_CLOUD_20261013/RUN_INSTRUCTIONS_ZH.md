# 云服务器执行说明

当前论文1恢复须先执行 `REDESIGN_HANDOFF_20261014/formal_numerical_execution/`
中的新数值输入验收；本文件旧启动命令是历史交付，不用于绕过旧失败注册。
诊断匹配不授权训练。dot 是共享 Pod 唯一操作者，按当前指令保持服务器运行，
本轮不执行 Stop/Terminate，也不替用户恢复或刷新预算。

## 开机与启动

使用 Linux NVIDIA 云服务器，安装 Python3.11/3.12（含venv）、git和NVIDIA驱动。启动器会核验或安装固定PyTorch2.8.0 / CUDA12.8。至少10GiB空闲空间，建议30GB可用工作空间。不要根据共享文件系统显示的 PB 容量推断你购买的配额。服务器总运行报价不得超过$0.75/小时；已批准的总$10预算和8小时任务期限继续有效。

最终发布后的固定版本命令见本文件末尾及聊天交付。复制完整命令到 Jupyter Terminal/SSH Terminal；不要逐行粘贴终端的 `root@...#` 提示符。

默认会询问实际每小时总价（可见输入）和 GH_TOKEN（隐藏输入，不显示字符）。GitHub token需仅授权项目仓库的Contents读写；不要在聊天里发送。无需RunPod API。R2备份为可选项；默认从官方源直接下载并核验，无需找回R2密钥。

出现 `DETACHED_WORKER_STARTED_NOT_SCIENTIFICALLY_COMPLETE` 和 job ID 后，程序脱离终端运行，可关闭本地电脑。收到 `NOT_STARTED_OR_BLOCKED` 或错误时不要当作已运行，不要重复新建训练。

## 进度与日志

将启动输出里的完整路径填入：

```bash
cat /workspace/mi-eeg-cloud/code-<revision>/research_runs/REDESIGN_CLOUD_20261013/jobs/<job-id>/job_status.json

tail -n 30 /workspace/mi-eeg-cloud/code-<revision>/research_runs/REDESIGN_CLOUD_20261013/jobs/<job-id>/supervisor.log
```

查看实时训练计数和source-only阶段：

```bash
cat /workspace/mi-eeg-cloud/code-<revision>/research_runs/REDESIGN_CLOUD_20261013/jobs/<job-id>/source/source_status.json
```

启动输出给出 `redesign/run-<job-id>` GitHub结果分支。启动回执不等于训练完成；以实际source计数、验证记录、完整结果和公开备份回执判断。

## 中断恢复

在原机器上保留磁盘、运行版本和原预算期限时，把相同启动命令最后一行加上 `--resume <job-id>`。GitHub凭据被拒时加 `--reset-credentials` 重新隐藏输入。不要改配置、seed、已冻结名单或统计规则。重复普通启动会提示已有任务，而不会消耗一个新的训练预算。

## 结束后

出现 `COMPLETED_EXPLORATORY_VALIDATED_GITHUB_BACKED_UP_MANUAL_STOP_REQUIRED` 表示数值验证与GitHub备份已通过。**到所在云平台控制台停止实例；本程序不会自动关机，退出后服务器仍可能计费。** 保留磁盘直到确认模型和结果备份。失败或预算到期且不准备立即修复时，也应手动Stop。

这些新增结果只能作为探索性外部评估，不能称为首次使用独立验证。原有Q1–Q16结果保持原样。


## 工作目录与锁修复

无需填写Pod ID、服务器IP或旧账号。默认使用 `/workspace/mi-eeg-cloud`，没有 `/workspace` 时使用 `~/mi-eeg-cloud`。AutoDL等平台可在命令最后加 `--work-dir /root/autodl-tmp/mi-eeg-cloud`（路径以该平台实际持久盘为准）。所有数据、任务和运行环境都在指定目录，密钥不会保存在该工作目录。

已将共享盘上的flock移到容器本地 `/tmp`。真正存在其他进程时仍会阻止启动；不得通过删除锁、删除注册或清空计数解决。已有旧版本注册的磁盘会显示原job和原版本，修复命令不会把它当作新任务，也不会刷新原八小时预算。不同服务器/UUID不自动续跑已拟合的任务；需要核对已有模型、冻结记录和预算。

## 启动包装进程检测修复

旧版本会把自身Python stdin预算包装进程参数里的 `cloud_supervisor.py` 路径误认为另一项运行任务。新版本只识别解释器实际执行的脚本，保留对真实运行任务的阻止；不要删除锁、任务注册、预算起点或训练计数。修复说明与独立回归测试见 `PROCESS_DETECTION_FIX_20261014.md`。

新服务器仍使用同一个通用启动器，无需填写Pod ID。实际每小时总价包含所有运行中的收费资源；按实际账单报价输入，不仅看GPU单价。未测试当前服务器实时状态；出现验证后的脱离终端启动回执才表示该服务器已启动工作进程。

固定执行版本见下方。默认直接从固定官方源云端下载，模型与统计结果自动备份GitHub。只输入当前云服务器总小时价与GH_TOKEN（隐藏输入）；无需RunPod API。额外R2备份加 `--r2`，指定实际持久盘加 `--work-dir <路径>`。完成或失败时请手动停止云平台实例。

## 通用固定执行版本

执行版本：`68b3bb56b59170c0fae9430740a4a10a6ab467c0`。已通过309项软件检查，其中37项覆盖进程检测；该版本36个包文件已按Git原始字节在公开GitHub逐一回读核验。未进行当前Pod实时检查或真实GPU训练。

```bash
curl -fSsL --retry 3 \
https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/68b3bb56b59170c0fae9430740a4a10a6ab467c0/research_runs/REDESIGN_CLOUD_20261013/LAUNCH_ON_GPU.sh \
-o /tmp/mi-eeg-launch.sh && \
bash /tmp/mi-eeg-launch.sh --revision 68b3bb56b59170c0fae9430740a4a10a6ab467c0
```

这是原探索性方案的软件启动修复，不重跑历史Q1–Q16。仍然要求实际CUDA预检、GitHub写入/回读、固定数据/输入检查和已提交source冻结。启动后运行source-only训练、target推理、独立验证和统计汇总；不进行target拟合。全流程受原批准预算/计数/期限约束，未通过门控就停止，不保证在任何新服务器上按时跑完。

请等待 `DETACHED_WORKER_STARTED_NOT_SCIENTIFICALLY_COMPLETE` 回执后再关闭终端或本地电脑；启动器打印实际job ID、状态文件、日志文件和GitHub结果分支。若提示已有任务，保留原记录并查看其状态，不通过更改工作目录或删除文件绕过任务或预算检查。完成、失败或期限到达均需手动停止实例计费。
