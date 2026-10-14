# 云服务器执行说明

## 开机与启动

选择 RunPod PyTorch2.8.0 / CUDA12.8 模板，Python3.11/3.12，一张 NVIDIA GPU，至少30GB实际可用工作空间。不要根据共享文件系统显示的 PB 容量推断你购买的配额。服务器总运行报价不得超过$0.75/小时；已批准的总$10预算和8小时任务期限继续有效。

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

在同一服务器保留磁盘、运行版本和原预算期限时，把相同启动命令最后一行加上 `--resume <job-id>`。GitHub凭据被拒时加 `--reset-credentials` 重新隐藏输入。不要改配置、seed、已冻结名单或统计规则。重复普通启动会提示已有任务，而不会消耗一个新的训练预算。

## 结束后

出现 `COMPLETED_EXPLORATORY_VALIDATED_GITHUB_BACKED_UP_MANUAL_STOP_REQUIRED` 表示数值验证与GitHub备份已通过。**到RunPod控制台点击Stop；本程序不会自动关机，退出后服务器仍可能计费。** 保留磁盘直到确认模型和结果备份。失败或预算到期且不准备立即修复时，也应手动Stop。

这些新增结果只能作为探索性外部评估，不能称为首次使用独立验证。原有Q1–Q16结果保持原样。

## 固定执行版本

执行版本：`abfb0b28d3f1d845fc85bd8ce0aad91fe99c7e25`。下面的命令无需填写任何密钥值：

```bash
curl -fSsL --retry 3 \
  https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/abfb0b28d3f1d845fc85bd8ce0aad91fe99c7e25/research_runs/REDESIGN_CLOUD_20261013/LAUNCH_ON_GPU.sh \
  -o /tmp/mi-eeg-launch.sh && \
  bash /tmp/mi-eeg-launch.sh --revision abfb0b28d3f1d845fc85bd8ce0aad91fe99c7e25
```

如需额外R2备份，在最后一行加 `--r2`。恢复时加 `--resume <job-id>`；凭据错误时再加 `--reset-credentials`。
