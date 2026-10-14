# 限定官方同字节源数据恢复修订

授权来源：父对话01a139a2-97f9-706d-bdb9-0c49bdd5b02a明确确认此前“本轮不重新下载/R2-only”仅为避免重复下载的执行安排，不是用户禁止官方获取；在用户“原始数据尽量直接在云端获取或从已验证存储恢复”的授权下，明确允许本次限定修订。当前Codex授权缓存已核实0/18，旧R2路径不可用。本记录不推定任何新R2权限或凭据已恢复。

范围仅限源域BNCI2014_001的18个冻结MAT（779873919字节），用于源输入故障诊断。禁止目标EEG、拟合、目标评估、数据范围扩张、改变输入/容差/划分/seed/预算。旧失败任务20261014T071918Z-exploratory-89b0c07d的0 fits/0 updates和根因未知记录保留。此独立传输工具不改R2-only训练流水线，也不授予训练启动。

## 固定身份和执行界限

- `source_official_manifest.json`逐项源自历史BNCI_R2_SOURCE_RECEIPT_20261003.json的official_url/size_bytes/sha256，并与Q8-E001/results/source_files.json一致。清单SHA256硬编码为e553d65cd86e5309e077ccfea21a9bee6020c5d9d5040de12089c2b859770b86。
- 独立Python标准库工具；默认只核对清单，不请求网络、不创建缓存。实际下载必须显式`--execute`。
- 单worker串行。每个缺失文件仅一次传输尝试，无自动重试。每次socket等待最多30秒；主监督进程限制整次worker为1800秒，超时TERM后最多5秒KILL。人工再次执行需查看既有失败记录，不能无限重试。
- TLS使用系统受信证书链，强制主机校验。只接受`https://bnci-horizon-2020.eu/database/data-sets/001-2014/<冻结文件名>`；重定向最多3次且只能回到同一主机和同一文件路径。不允许HTTP降级、其他域名/端口、凭据、query、fragment或其他MAT路径。禁用环境代理。若官方站迁移，需要父对话审核，不自动放宽白名单。
- 所有现存缓存先完整大小/SHA256验证，再开始任何请求。正确缓存复用；异常缓存和符号链接阻塞，不下载替代品覆盖它们。
- 临时文件`.AxxS.mat.<attempt>.partial`仅在完整流大小+SHA256及二次文件读取通过后，以排他链接提交为最终MAT，竞争产生的最终文件不覆盖。失败和超时的临时文件保留，不能当作完整原始文件；不自动续接未经核实的partial。
- 原文件最终全部再次完整验证。ETag、HEAD和Content-Length均不能代替最终内容哈希。存在Content-Length时额外核对，但没有该头仍需完整size/SHA256匹配。
- 导入前检查所有缺失文件总大小+6GiB余量；不打包第二份归档。锁防止同一缓存根并发下载；原文件和日志必须放在Git checkout之外。

## 父对话执行步骤

实际下载由父对话现有Jupyter终端执行。本Codex只完成脚本、固定清单和离线测试，未探测官方网站、未读取EEG、未下载。

先获取本目录固定提交的`restore_source_official.py`、`source_official_manifest.json`，核对交付的两项SHA256后运行。此工具仅用标准库，可用已安装诊断环境解释器，不再安装环境。

```bash
/workspace/paper1-diagnostic-runtime/bin/python restore_source_official.py \
  --data-dir /workspace/paper1-readonly-probe/data \
  --evidence-dir /workspace/paper1-readonly-probe/official-transfer-evidence
```

以上为dry-run。检查输出18文件/779873919字节后，同命令追加`--execute`才实际下载。监督结果写`<attempt>-supervision.json`，传输进度/结果写`<attempt>-transfer.json`，子进程日志写`<attempt>-worker.log`。完整下载门槛是worker_exit_code=0且transfer状态`ALL_SOURCE_ORIGINALS_EXACT_BYTES_VERIFIED_NOT_INPUT_RECONSTRUCTION`、18项覆盖并完整哈希一致。超时receipt可能保留最后STARTED状态；supervision的124/timeout优先解释，不是成功。不要把进程退出当作实例停止。

失败保留全部记录及partial，先看HTTP状态/错误类型和监督超时记录。不得删旧记录换目录重置计数/预算，也不得把网络失败认定成旧数组哈希错误的根因。

## 后续本地缓存模式输入重建

诊断源码仍使用已交付固定版本`c802e65709103189becf7e6ff3a55c99a405a7e8`，并必须具备科学基线`eae194514def23e5d1ec6cbb117d4f84fc6f067f`的Git对象。已有正确checkout则复用，不重新初始化；浅克隆缺基线才定向获取：

```bash
git fetch --depth 1 origin eae194514def23e5d1ec6cbb117d4f84fc6f067f
```

在固定c802e657诊断checkout根目录，原文件18/18验证成功后执行：

```bash
/workspace/paper1-diagnostic-runtime/bin/python \
  research_runs/REDESIGN_CLOUD_20261013/scripts/reconstruct_source_readonly.py \
  --data-dir /workspace/paper1-readonly-probe/data \
  --output /workspace/paper1-readonly-probe/new-host-source-report.json
```

不带`--import-r2`，不需R2凭据、不访问目标数据。已有同名报告拒绝覆盖，须保留并使用新的明确报告名。使用既有已验证NumPy2.3.5/SciPy1.17.0/pandas2.2.3环境，不以系统NumPy2.1.2运行。逐文件原始身份通过后，还必须核验2592试次整体/逐trial输入哈希及labels/metadata/IDs、SOS；任何不符保留报告并阻塞。成功只说明新机器重建符合冻结身份，不说明旧错误根因已解决，不放行拟合。

## 证据与停止条件

传输清单、脚本身份、全部attempt记录与源重建报告应经私人Library/已验证传输离机保存并独立回读SHA256；不要把受限原始EEG或凭据上传公共GitHub。已有旧预算限额和父对话共享实例停机协调不变；不创建付费资源、不自动停机、不重置旧预算。本工具最多30分钟下载窗口是本次诊断的附加运行上限，不是新GPU预算。平台计费和其他任务依赖仍由父对话确认。
