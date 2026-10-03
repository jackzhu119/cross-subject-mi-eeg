# Q15 RunPod raw transport and restart workflow

This release downloads the existing 160 Cho2017 / Lee2019_MI original MAT objects directly from private Cloudflare R2 onto the current RunPod, verifies their full contents, saves receipts back to R2, and requests **Stop Pod** after its final verified backup. The user's Windows computer is not in the data path.

**Scientific gate:** `fits_started = 0`. Real raw metadata audits and the preprocessing freeze are incomplete. This release downloads and verifies; it does not train. Cho/Lee files are external audit/evaluation data; source training also requires 18 separately verified BNCI2014_001 originals.

## 新服务器启动

在 RunPod 的 **Connect → Enable web terminal** 打开终端，或者使用 **Jupyter → Terminal**。无需先配置 SSH，运行：

```bash
curl -fSsL --retry 3 --connect-timeout 20 --max-time 180 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/q15/cloud-bootstrap-20261002/research_runs/Q15-CLOUD-AUTOMATION-20261002/LAUNCH_ON_RUNPOD.sh -o /tmp/q15-launch.sh && bash /tmp/q15-launch.sh
```

稳定入口会下载固定提交的两个 Python 文件并核对 SHA-256。不要继续使用之前报错的旧提交命令。服务器从自己的 `RUNPOD_POD_ID` 读取身份；不会绑定历史服务器或截图中的固定 ID。

如果旧磁盘保存了私有配置，脚本会复用并重新验证。缺少的字段会逐一隐藏询问。输入时不显示字符是正常行为：粘贴后按一次 Enter。不要把凭据放在命令、聊天、截图或 GitHub 中。Cloudflare 页面上用于 **S3 clients** 的 Access Key ID、Secret Access Key 和账户 endpoint 对应 R2 字段；页面顶部 Cloudflare API Token 不是 S3 Secret Access Key。

RunPod API key 必须有访问当前 Pod、执行 Stop 的权限。读取 Pod 成功不能证明 Stop 权限。旧缓存密钥被 401/403 拒绝时，会先尝试不同的当前服务器环境密钥；仍被拒绝则只重新询问 `RUNPOD_API_KEY`，保留四个 R2 字段。

等出现 `detached_download_supervisor_started_training_not_started` 和 PID 后，后台任务才得到启动确认，可以关闭本地浏览器和电脑。`NOT_STARTED`、`LAUNCH_PENDING_NOT_CONFIRMED` 或仅下载了脚本，都不表示任务已部署成功。

## 已有磁盘、断点续传和下次启动

私有配置、可重复执行的入口和状态放在 `/workspace/.q15-cloud/`，目录权限 0700，凭据文件 0600，位于 Git 之外。原始数据放在 `/workspace/q15-data/raw/`。共享磁盘迁移后会重新核验当前 Pod；发现另一个 Pod 的 supervisor 持有锁会报出冲突，防止同一磁盘上并行下载或误报启动成功。

在首次运行新版本后，下次服务器启动可执行：

```bash
bash /workspace/.q15-cloud/start.sh
```

这个持久入口默认非交互，凭据完整时无需再输入。它只使用已保存配置或当前环境变量；缺少字段会明确说明字段名称。持久入口文件本身不会修改 RunPod 的模板启动命令，**尚未设置“开机自动运行”**。新版本尚未在用户的 Pod 上安装或实测；首次运行上面的稳定入口才会创建它。

已有完整文件必须重新通过全量 SHA-256/MD5 检查才复用。`.part` 文件只在对象 ETag 和预期内容身份一致时续传，写入后还会独立从磁盘完整读取验证。不会因为文件存在、元数据匹配、文件数相同或空间预算通过就把内容标为正确。

空间预算使用真实的已分配文件块和认证库存，按“剩余下载量 + 20 GiB 余量”检查。若数据已迁移但库存缓存没有迁移，会先从固定 SHA 的约 4.7 MB 私有来源档案恢复认证库存，再计算剩余空间。

## 磁盘容量

160 个原始文件共 75,551,469,122 字节（约 70.36 GiB）。下载阶段要求实际分配容量不少于 95 GiB，建议 Volume Disk 至少 **120 GB**；未来训练的空间需求仍需按最终预处理方案重新估算。`df` 显示的 2.1 PB 是共享存储池，不能证明购买额度。

脚本通过当前 Pod API 请求 `includeNetworkVolume=true`，读取实际挂载到 `/workspace` 的 network volume 或 volume disk 容量。如果 API 未提供额度，会保留凭据并退出，不凭共享 `df` 推断购买容量。查看 RunPod **Volumes** 中实际购买的 GB 后，以该数值运行，例如实际为 200 GB 时：

```bash
bash /tmp/q15-launch.sh --volume-gb 200
```

已知不足的 API 额度不能被手工值覆盖。手工额度只对提供它的当前 Pod 生效，迁移后不能继承旧 Pod 的声明。

## 检查、恢复和故障诊断

仅做预检，不下载大文件、不启动 worker、不停止 Pod：

```bash
bash /tmp/q15-launch.sh --check-only
```

首次新版本运行后，可使用持久入口查看安全状态或仅重录一个字段：

```bash
bash /workspace/.q15-cloud/start.sh --status
bash /workspace/.q15-cloud/start.sh --interactive --reset-credential RUNPOD_API_KEY
```

`--reset-credential` 只接收字段名称，绝不接收密钥值。可替换的字段是 `R2_BUCKET`、`R2_ENDPOINT`、`R2_ACCESS_KEY_ID`、`R2_SECRET_ACCESS_KEY`、`RUNPOD_API_KEY`。使用 `--interactive --check-only` 可以允许隐藏输入并仅验证。

预检逐阶段输出安全 JSON，私有 `last_bootstrap_report.json` 记录阶段和具体错误代码。不会再把身份检查错误折叠成无信息的 `IntegrityError`。

| 安全错误代码 | 处理 |
| --- | --- |
| `runpod_api_edge_policy_denied_http_403` | 网络防护拒绝；不重新询问密钥，不反复重试，检查 Pod 网络限制或联系 RunPod 支持。 |
| `runpod_api_http_401` / `runpod_api_http_403` | 只重新输入有当前 Pod 访问权限的 RunPod API key；R2 字段保留。 |
| `runpod_api_http_404` | 核对当前 Pod 是否属于该密钥账户，不手工使用旧 Pod ID。 |
| `runpod_api_pod_identity_mismatch` | API 响应身份不匹配，停止启动并排查；不请求停止其它 Pod。 |
| `runpod_pod_locked_stop_forbidden` | 当前 Pod 被锁定，无法自动 Stop；解除该 Pod 的锁后重试。 |
| `shared_volume_worker_belongs_to_different_pod` | 旧 Pod 仍有共享磁盘 supervisor，先核实并停止旧任务再启动此 Pod。 |
| `configured_workspace_volume_quota_unknown` | 从 Volumes 获取实际 GB，再用 `--volume-gb N` 提供。 |
| `s3_AccessDenied` / `s3_InvalidAccessKeyId` / `s3_SignatureDoesNotMatch` | 核对桶权限或相应 S3 字段，仅重录有问题的字段。 |
| `LAUNCH_PENDING_NOT_CONFIRMED` | 启动尚未确认；先 `--status` 查看，锁和进程检查会阻止重复 worker。 |

## Durable evidence and stopping

The provenance archive SHA-256 is `332b878514894f7e6543c652e4138be13d8125ac8da20099ae9ca8641684fa0b`. Its pinned inventory SHA-256 is `6dc6728e3d8b84c405249845b3dd346d75ba74218e603d5ad8584b0ded93b62a`. Archive extraction rejects unsafe paths and links. No storage receipt authorizes preprocessing or fitting.

Progress and final receipts use private `q15/cloud-jobs/` prefixes. Every final status, log and backup manifest is uploaded, fully read back and hashed before the official `POST /v1/pods/{currentPodId}/stop` request. There is no terminate/delete operation or container shutdown command. Scientific blocks and supported-work failures are recorded before stopping; if identity, backup or Stop verification fails, the worker reports that shutdown is unconfirmed. API acceptance is not proof of physical shutdown. Stopped Pod volumes can still incur storage charges.

The API identity is checked before work and again before Stop. Startup and worker locks prevent duplicate jobs. Credential values are absent from commands, public receipts, exception output and child environment. Runtime copies preserve a tested entry point on the persistent volume.

## RunPod API network-edge fix

Public unauthenticated probes reproduced a Cloudflare 1010 denial with Python urllib's default client signature. The same endpoint accepted an explicit, accurate `q15-cloud-transport/20261003` application User-Agent and returned the expected authentication failure for a synthetic invalid key. GET and Stop now consistently identify this application. No browser identity is impersonated, no authentication is removed, and no proxy/TLS setting is bypassed.

A recognizable network-edge denial is separately classified as `runpod_api_edge_policy_denied_http_403` and does not trigger secret re-entry or automatic identity rotation. Ordinary RunPod authentication denials retain their previous codes. The user's previous 403 body was not available, so this reproduction does not establish that every prior 403 was caused by the network edge. Real current-Pod authentication remains to be verified by the new release.

## Release validation and limitations

See `PREPARATION_RECEIPT.json` and `RELEASE_VALIDATION.json` for the exact commit, checksums and test counts. Automated tests use fake credentials, a memory object store and synthetic HTTP/process fixtures; they do not run models or actually stop a Pod. Managed-cloud live R2 tests separately verify list/write/full readback/delete and restoration of the real pinned archive and 160-file inventory.

These checks are **not authenticated validation of the user's RunPod**. The latest old-version attempt was `NOT_STARTED` at the RunPod API identity preflight with an opaque `IntegrityError`. The next release reported HTTP 403 after three authentication attempts; its response body was not logged, so API authorization denial and network-edge denial could not be distinguished. The new Pod screenshot establishes that the Pod is running, not that credentials or this supervisor are deployed. First successful preflight and worker handshake on that Pod are still required.

## Research continuation

Implement and independently review real provider adapters; audit all 160 originals; resolve preprocessing amendments; verify the source BNCI originals; commit actual freeze inputs and a pre-fit receipt on the final execution machine. Only then can the reviewed source runner train. Some existing dry-run commands exit zero while reporting a block, so exit code alone cannot authorize fitting. Independent source validation and checkpoint freezing are also required before external Q15 evaluation.

Paper archive: [PR #1](https://github.com/jackzhu119/cross-subject-mi-eeg/pull/1). [Research handoff](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper/non-q15-manuscript-20261002/research_runs/PAPER_PUBLICATION_20261002/CONTINUE_IN_ANOTHER_CHAT.md).
