# Q15：旧 Pod 无法访问时，从 R2 恢复并完成云端运行

`from-r2` 在新 RunPod 上恢复 GitHub 已保存且经过验证的 **15 次源域训练成果**，从 R2 下载完整原始数据，重新生成外部数据预处理文件，再执行推理、独立验证和 GitHub 结果发布。整个流程在云端完成；新服务器的 `new_source_fits = 0`、`target_fits = 0`，累计源域训练数为 15。

恢复依据固定为提交 `782d2d0070a50c37d13c8e9f1cab3b3b81bac4fc`，科学代码固定为 `271af288a2f3863430ab80e3145c2dee9bd5571d`，来源作业为 `20261004T005335Z-9b3bce30277a`。新运行生成独立的作业 ID 和结果分支，并保留原模型、训练账本及运行环境来源记录。

## 1. 创建新 Pod

建议配置：

| 项目 | 配置 |
|---|---|
| GPU | 1 张 RTX 4000 Ada，或满足显存需求的 NVIDIA GPU |
| 模板镜像 | `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` |
| Python | 3.12 |
| PyTorch / CUDA 运行库 | `2.8.0+cu128` / 12.8 |
| 持久磁盘 | `/workspace` 购买 200 GB，运行期间保持挂载 |
| HTTP 端口 | 标签 `Jupyter`，端口 `8888` |
| TCP 端口 | 标签 `SSH`，端口 `22` |

端口配置需要镜像中的 Jupyter/SSH 服务配合。优先使用上述官方 PyTorch 模板。RunPod 网络磁盘的 `df -h` 可能显示共享文件系统总容量，购买容量应以 RunPod 控制台为准。

完整恢复包括 18 个 BNCI 原始文件和 160 个 Cho2017 / Lee2019_MI 原始文件，共约 **76.33 GB**。恢复后还会生成 52 人 Cho2017 和 54 人 Lee2019_MI 的预处理文件，并保留模型、运行环境和验证文件。

## 2. 准备凭据（手动停机需要五项）

可在新 Pod 的 Secrets 中配置下列变量，或者在启动脚本的隐藏提示处逐项粘贴。隐藏输入不会显示字符，粘贴后按一次 Enter。不要把凭据放进启动命令、截图、GitHub 文件或聊天。

| 变量名 | 来源及用途 |
|---|---|
| `R2_BUCKET` | 保存 Q15 数据的 R2 存储桶名称 |
| `R2_ENDPOINT` | 该 Cloudflare 账号的 R2 S3 endpoint |
| `R2_ACCESS_KEY_ID` | 有权访问该存储桶的 S3 Access Key ID |
| `R2_SECRET_ACCESS_KEY` | 配套的 S3 Secret Access Key |
| `GH_TOKEN` | 能写入 `jackzhu119/cross-subject-mi-eeg` 的 GitHub token；细粒度 token 选择该仓库，授予 **Contents: Read and write** |
| `RUNPOD_API_KEY` | 仅自动停机模式需要；本页 `--manual-stop` 流程不需要、不询问、不传递该值 |

R2 权限须支持 list、read、write 和 delete，以完成独立探针。本页默认使用 `--manual-stop`，只需要四项 R2 配置及 `GH_TOKEN`，结束后由用户在 RunPod 控制台停止 Pod。

手动模式先检查 GitHub 仓库权限，前台通过标识为 `github_preflight_verified_manual_stop`。之后才收集缺失的 R2 值、安装 S3 客户端并启动后台任务；后台仍会复核代码、GitHub、固定运行环境、CUDA、原始数据及科学门禁。启动、恢复、推理、成功和失败处理均不访问 RunPod API。Pod ID 仅来自 Pod 环境，状态明确记录其未经 API 身份认证。

手动模式无法从 RunPod API 核验购买的磁盘配额，状态记录 `workspace_purchased_quota_verified = false`、`disk_capacity_gb = null`。空间检查使用文件系统报告的可用字节，实际写入仍受存储配额约束；共享存储池的可用空间不等于购买配额。

## 3. 在新 Pod 的 Jupyter Terminal 启动

复制整段执行：

```bash
curl -fSsL --retry 3 \
  https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/5efbd3e194da839b4b68094b8173b102f4983982/research_runs/Q15-MIGRATION-20261004/Q15_MIGRATE_ON_RUNPOD.sh \
  -o /tmp/q15-migrate.sh &&
bash /tmp/q15-migrate.sh from-r2 --manual-stop
```

这个入口不需要旧 Pod 终端、旧磁盘或迁移归档。脚本会验证固定版本的辅助文件，前台验证账号，再安装私有运行环境并启动后台作业。凭据仅在当前启动进程及后台任务内传递，脚本不将它们保存到 `/workspace`。重新执行时，只有 Pod Secrets 等已有环境配置可以自动提供凭据；上一次子脚本的隐藏输入不会保存到下一次执行。

终端出现 `detached_migration_started_not_scientifically_complete` 只表示已发起后台运行。请继续检查下面的状态；待新 Pod 预检通过、状态进入 `r2_original_download_running` 且 `files_verified` 开始增加后，可以关闭本地电脑和浏览器。保持云端 Pod 运行以及持久磁盘挂载。

## 4. 查看进度和结果

在 Pod 中执行：

```bash
JOB_ID=$(python3 -c 'import json; print(json.load(open("/workspace/q15-migration/jobs/current_job.json"))["job_id"])')
cat "/workspace/q15-migration/jobs/$JOB_ID/migration_status.json"
tail -n 30 "/workspace/q15-migration/jobs/$JOB_ID/supervisor.log"
```

需要查看科学运行状态时执行：

```bash
cat "/workspace/q15-execution/jobs/$JOB_ID/job_status.json"
```

正常顺序为：GitHub 和运行环境预检 → R2 list/write/read-back/delete 探针 → 原始文件下载与 SHA256/大小核验 → 106 人预处理文件重建及来源核验 → 原模型和预处理独立复核 → 推理冻结提交及远端读回 → 外部推理 → 独立科学验证 → 结果提交及远端读回 → 用户手动停止当前 Pod。

原始 EEG 和恢复生成的 NPZ 文件保存在云端磁盘；GitHub 发布审计、冻结、验证、结果及发布证据。新结果分支为 `q15/run-<JOB_ID>`，启动输出和 `current_job.json` 均记录该分支。公开状态路径为：

```text
research_runs/Q15-MIGRATION-20261004/jobs/<JOB_ID>/job_status.json
```

下载或预处理时 GPU 利用率可能很低。完成判断以文件中的独立验证和发布回执为依据。`completed_with_calibration_limitations` 表示科学验证通过且报告保留原始电压标定未核验的限制；完成时还应核对 `github_results_backup_verified = true`，以及同一公开作业目录的 `publication_evidence.json`。该回执记录已验证的结果提交 SHA 和文件哈希。手动模式始终记录 `automatic_shutdown_enabled = false` 和 `shutdown_status = manual_stop_required`，不会生成 Stop API 接受回执。

## 5. 中断后恢复

如果同一持久磁盘仍挂载，且上次后台进程已经停止，请使用**相同作业 ID**恢复。原始文件下载支持部分文件续传；已完成文件仍会重新核验，原模型继续复用。

```bash
JOB_ID=$(python3 -c 'import json; print(json.load(open("/workspace/q15-migration/jobs/current_job.json"))["job_id"])')
curl -fSsL --retry 3 \
  https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/5efbd3e194da839b4b68094b8173b102f4983982/research_runs/Q15-MIGRATION-20261004/Q15_MIGRATE_ON_RUNPOD.sh \
  -o /tmp/q15-migrate.sh &&
bash /tmp/q15-migrate.sh from-r2 --manual-stop --job-id "$JOB_ID"
```

如果提示 `A migration worker is already active`，现有后台进程仍持有运行锁，请继续观察现有作业。不要为同一磁盘同时启动多个作业。手动恢复启动仍需四项 R2 配置和 `GH_TOKEN`；可由新 Pod Secrets 提供。

### 账号预检拒绝时重试

前台错误码会区分服务：`runpod_account_api_http_403` 来自 RunPod 请求，`github_account_api_http_403` 来自 GitHub 请求。401、403、404 或 GitHub 写权限未确认时，脚本会只要求重新隐藏输入对应密钥，最多尝试三次；其他值只在本次进程内保留。网络错误不会被当作换密钥可解决的问题。预检未通过时，不启动迁移 worker、不下载 R2 原始数据，也不请求停止 Pod。

旧版本的 `account_api_http_403` 同时用于两家服务，不能凭该错误确定拒绝方。如果启动时没有询问某个变量，只能说明脚本继承了可接受格式的值，不能证明该值有效。可用重复的 `--reset-credential NAME` 强制重新输入指定项；允许名称为本页列出的六项变量。该参数只替换本次脚本进程内的值，不修改控制台 Secrets。

针对已确认在账号预检阶段失败的作业 `20261005T050511Z-migration-from-r2-b82ad79b`，下载本页固定入口后执行：

```bash
bash /tmp/q15-migrate.sh from-r2 --manual-stop \
  --job-id 20261005T050511Z-migration-from-r2-b82ad79b \
  --reset-credential GH_TOKEN
```

这里只提示隐藏输入 GitHub token，之后询问缺失的四项 R2 值，不询问 RunPod key。这里只重试已失败的同一作业，不重新训练已经验证并保存在 GitHub 的 15 次源域模型。

## 6. 自动停止及需要人工处理的情况

本页的 `--manual-stop` 完成后保留 Pod 运行，用户确认结果及 GitHub 发布回执后，在控制台点 Stop。数据校验或 GitHub 备份失败时，查看 `error_code` 和 `shutdown_status`，据此处理；不能把后台启动回执当作完成回执。

不带 `--manual-stop` 的原自动停机模式仍保留。该模式需要当前新 RunPod 账号的 API key，并验证新 Pod 身份；只有完成结果或失败状态已提交 GitHub 并通过远端读回后，才允许请求停止当前新 Pod。其 `accounts_preflight_verified` 只证明账号读请求通过，不单独证明 Stop 写权限、R2 可用性或科学运行完成。

Stop API 接受请求不等于已确认服务器物理停机。请在 RunPod 控制台确认 Pod 状态；停止后持久磁盘仍可能计费。在需要保留恢复能力时继续保留磁盘，待确认所需数据和结果已保存后再处理存储。

`backup` 和 `restore` 是保留的迁移归档入口。旧 Pod 已无法访问时，使用本页的 `from-r2` 流程即可。
