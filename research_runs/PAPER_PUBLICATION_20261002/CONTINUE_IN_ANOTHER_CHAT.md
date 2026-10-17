# 在其他聊天接续 / Continue in another chat

## 先读取这些记录

仓库：`jackzhu119/cross-subject-mi-eeg`。请读取 `paper/non-q15-manuscript-20261002` 分支及其草稿 PR；此分支保存英文论文、中文说明、图表、补充清单和核验记录。论文路径为 `research_runs/PAPER_DRAFT_20261002/`，存储回执路径为 `research_runs/PAPER_PUBLICATION_20261002/publication_receipt.json`。

原论文 ZIP SHA-256：`b70c648caf0b4a77dfa261d42eadd30c890fbe1986fb2abd7007cf62502267ae`。该 ZIP 含 49 个文件。论文为作者审阅稿；作者、伦理、基金、目标期刊等仍待核实。原稿里的“尚未推送/发布”描述的是之前的论文整理阶段，本次归档记录见本目录 README 和存储回执。

R2 备份前缀：

```text
papers/non-q15/20261002/b70c648caf0b4a77dfa261d42eadd30c890fbe1986fb2abd7007cf62502267ae/
```

其中 `handoff_private.json` 保存 RunPod 连接状态、当前工作区路径及下一步。需要通过当前环境配置的 R2 凭据读取，禁止打印凭据或把私钥、密码、token 提交到仓库。新聊天或新环境不会自动继承之前的私钥、进程和登录状态。

## Q15 当前状态

- 官方 Cho2017 / Lee2019_MI 原始 MAT 共 160 个、75,551,469,122 字节，已上传 R2；这一结论来自原始存储核验记录，不代表科学审计已经完成。
- 154 个文件已完成 R2 全字节读回；6 个 Lee2019_MI 文件目前有来源/对象 multipart 完整性证据，仍须完成全字节读回。
- `fits_started = 0`、`source_fits = 0`、`target_fits = 0`。
- 科学原始数据元信息审计未完成，`preprocessing_contract_frozen = false`。用户已授权后续自主执行与训练，但这些前置门槛仍然有效。
- RunPod 的用户终端已验证 RTX 4000 Ada 约 20 GB 显存、PyTorch 2.8.0+cu128、CUDA 12.8 和一次 GPU 张量计算成功；这不代表训练已启动。
- Codex 尚未建立该 Pod 的认证连接，也未部署后台作业。直接 SSH 路由尚未打通；Jupyter 代理地址在用户浏览器可用，但 Codex 请求返回 HTTP 403 / Cloudflare 1010，尚未到达 Jupyter 登录。不要把它误判为已连接或单纯缺少 Jupyter token。
- `/workspace` 的 `df` 结果是共享存储容量，不能当作购买的 Pod 磁盘额度；实际配额尚未核实。

## 恢复原始数据和审计记录

已有私有 R2 原始数据审计/传输证据归档：

```text
q15/provenance/20261001T093410835515Z-614d381fb70141d7b91a85ae4eb907a8/archive.tar.gz
```

SHA-256：`332b878514894f7e6543c652e4138be13d8125ac8da20099ae9ca8641684fa0b`，4,708,471 字节。同一前缀的 `index.json`、`READINESS.json`、`transport_verification.json` 和 `upload_receipt.json` 提供文件索引与核验依据。该归档包含 847 个证据/代码文件，不包含原始 EEG 本体。归档中的旧授权和连接字段是历史快照，应结合本次接续记录与最新实际检查判断。

在原始工作区，可读取 `research_runs/Q15-DATA/READINESS.json`、`RESUME_STATE.json`、`r2_source_storage_verification.json` 及 `r2_cloud_handoff_archive_receipt.json`。迁移环境时，先恢复上述归档并检查哈希及安全成员路径，再通过核验记录定位已有 R2 原始对象，避免重复下载全部数据。

剩余 6 个全字节读回文件：

```text
session1/s52/sess01_subj52_EEG_MI.mat
session2/s29/sess02_subj29_EEG_MI.mat
session2/s37/sess02_subj37_EEG_MI.mat
session2/s54/sess02_subj54_EEG_MI.mat
session2/s45/sess02_subj45_EEG_MI.mat
session2/s52/sess02_subj52_EEG_MI.mat
```

## 后续顺序

1. 检查当前云环境、R2 凭据是否 present 与网络路由；不输出任何凭据值。重新核实 Pod 状态和可用认证方式，建立获授权的连接。
2. 从 R2 恢复证据和所需原始对象，在云端完成 6 个剩余文件的全字节读回核验。数据不经过 Windows 本地电脑。
3. 完成全部 160 个原始文件的科学元信息审计与独立复核；解决离散 cue/endpoints、原生导出单位、Cho MAT reference，以及 trial/run/boundary/context/padding/filter 定义、源被试群一致性和 21 通道映射等未决事项。
4. 形成可审阅的审计结论，冻结 preprocessing contract。冻结之前保持 `fits_started = 0`。
5. 门槛通过后按用户已有授权继续云端预处理、训练及结果保存，采用脱离浏览器/SSH 会话的后台进程，日志和 checkpoint 回存 R2；先记录真实启动状态再告知可关闭本地电脑。

可在新聊天粘贴：

> 请先读取 GitHub 仓库 jackzhu119/cross-subject-mi-eeg 的 paper/non-q15-manuscript-20261002 分支中 research_runs/PAPER_PUBLICATION_20261002/CONTINUE_IN_ANOTHER_CHAT.md 和 publication_receipt.json，再继续 Q15。论文已归档；原始 EEG 已在 R2。不要打印凭据，不经 Windows 传数据；保持 fits_started=0，直到原始数据审计完成且 preprocessing contract 冻结，然后按已有授权继续云端训练。
