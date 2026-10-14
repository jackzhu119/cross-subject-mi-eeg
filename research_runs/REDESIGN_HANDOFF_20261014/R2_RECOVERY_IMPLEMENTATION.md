# R2-only 导入与易失盘恢复实现

本轮：代码实现、合成测试、Codex隔离诊断环境安装验证；0次真实EEG读取/下载、0次新增R2请求、0次GPU拟合。此前401后未重试。生产启动仍pending；下面环境准备和诊断命令由父对话安排，不能据此直接训练。

## 已实现

`REDESIGN_CLOUD_20261013/scripts/r2_only.py`：映射必须与冻结192文件集合逐项匹配相对路径、尺寸和SHA256；缺项、多项、重复key、越界路径或符号链接拒绝。只读已有安全环境绑定，不提示/创建持久凭据。不调用List、不猜对象key、不下载官方源。缓存逐字节验证；缺文件从R2串行流式写临时文件，验证完整SHA256后以排他链接提交。错误不覆盖已有文件、不保留无效临时副本、不回退官方源。导入前要求全部缺失数据空间加6GiB余量。

`prepare_data.py` 的实际流水线先走上述导入，再以禁止下载模式读取源缓存、以 `download=False` 审计目标缓存。历史 `source_one` 的显式下载辅助能力留作旧回归测试，但生产prepare入口不使用它。冻结源/目标数组、名单、标签、原生context、逐试次哈希门控均保留。

`private_recovery.py`：训练writer同步快照，不从后台复制变化中的恢复状态。每次消耗fit ordinal或optimizer update之前，先用远端条件写入和完整GET回读确认PENDING；提交本地batch state与ledger后，备份模型/optimizer/RNG/order/offset、登记/预算、配置冻结引用及完整脱敏日志前缀。核对fit数、active fit身份与ledger更新计数；未消解的local intent禁止提交快照。所有内容以SHA256 key存私有R2，使用If-None-Match排他创建，绝不覆盖旧快照引用的内容；同一writer会话中已完整回读的未变内容复用。新manifest回读通过后最后CAS更新HEAD为COMMITTED，并回读确认。ETag只用于并发条件，不作为字节校验。

远端PENDING、写入结果不确定、HEAD竞争、manifest/blob损坏、磁盘不足均停止；不自动重试不确定写操作。容器丢失时宁可阻塞，也不从旧快照重复可能已发生的更新。已确认COMMITTED可下载成新审核目录；目录已存在就拒绝，无修改活动注册/预算/机器锁或自动迁移的能力。

运行中的私有快照不包括原始EEG和目标输入张量，不进公共GitHub。原公开备份继续覆盖已完成模型、预测、统计和校验回执。私有完整日志备份发生在结束阶段；失败日志单独使用不可变receipt，绝不清除训练PENDING。最终 `completed_backup_receipt.json` 只在新模式私有终端日志验证成功后写出。关闭服务器前仍核对该文件、私有log receipt和GitHub完整回读，worker exit不等于停机。

限制：日志单次捕获最多64MiB、单恢复文件最多256MiB、快照总量最多2GiB；超限阻塞，不静默截断。捕获完整已写入日志前缀并登记原始字节数；已知注入密钥、凭据赋值行和带query的URL脱敏。新生成的后续日志须在worker退出后再用backup-stopped-worker-log命令备份。机器突然丢失时最后一次快照之后尚未刷新的日志可能丢失，不能宣称零日志损失。

本地不打大归档；最多增加64MiB脱敏日志临时副本。开始快照前保留5GiB+64MiB空闲；恢复目录下载前核算manifest全部字节+5GiB。R2保留不可变历史版本；本轮没有自动删除R2快照的行为。每batch同步远端操作增加耗时/请求/存储费用，尚无真实速度基准，原8小时截止保持，不能保证在旧期限内完成。

## 新Pod只读重建：先解决输入，不创建训练任务

父对话确认新Pod没有旧工作根/注册/预算/源文件/环境；A4500、30GB overlay，不是旧RTX2000 Ada现场。新Pod当前numpy2.1.2不合格；host torch2.8.0+cu128可供后续训练环境复用，但不用于诊断环境。

固定检出本交付提交后，先确保浅克隆含旧科学基线：`git fetch --depth 1 origin eae194514def23e5d1ec6cbb117d4f84fc6f067f`。然后在父对话确认安排下执行：

```bash
bash research_runs/REDESIGN_CLOUD_20261013/PREPARE_DIAGNOSTIC_ENV.sh /workspace/paper1-diagnostic-runtime
```

只创建一个新且隔离的Python3.12 venv，不继承site-packages，不装Torch/CUDA，不读取数据或创建任务。依赖包含固定numpy2.3.5、scipy1.17.0、pandas2.2.3、boto3 1.40.61及其完整已实测锁定的传递依赖；安装不使用pip缓存，pip check与精确版本断言必须通过，现有同名环境不会被覆盖。该脚本已在Codex实际执行成功，见 `diagnostic_environment.json`；未在RunPod执行。

仅在R2安全访问恢复后：

```bash
/workspace/paper1-diagnostic-runtime/bin/python research_runs/REDESIGN_CLOUD_20261013/scripts/reconstruct_source_readonly.py \
  --data-dir /workspace/paper1-readonly-probe/data \
  --output /workspace/paper1-readonly-probe/new-host-source-report.json \
  --import-r2 \
  --mapping research_runs/REDESIGN_HANDOFF_20261014/source_r2_mapping.json \
  --mapping-sha256 7d5ec2e9ddec16d2be5cb3778037c96dabb6559b8c208ad4cca9923c67407663
```

此清单来自既有Q15 R2备份收据，18文件779,873,919 bytes，离线核对与Q8冻结身份全部一致；并不声称这些对象现可读取。该命令不要求GH token，不处理目标数据；仅使用既有注入R2绑定。输出必须是新文件且在checkout外。数据缓存禁止放入checkout。失败保留已有有效文件，但不改注册/预算、冻结值或科学代码。

已有验证缓存时去掉 `--import-r2 --mapping ... --mapping-sha256 ...` 即可只读本地重建。报告包含整体/逐trial哈希、label/metadata/id、SOS系数、NumPy CPU特性、精确运行版本以及冻结文件SHA。内部逐个与旧 `eae1945` Git原始字节比较6个科学输入文件；需要checkout可读取该历史commit。任何实际输入不匹配时输出BLOCKED并exit2，不使用容差替代哈希。

## 旧现场丢失后的科研恢复条件

1. 保留旧失败分支和0 fits/0 updates证据，明确标记旧现场不可用、旧错误根因未知。新Pod不能生成“旧现场已修复”的证据。
2. 新机器源文件/2592试次完整精确重建通过；再完成174个目标EDF的实际R2映射和逐文件/逐trial冻结检查。当前没有目标R2 key清单，不能发布可运行的完整192文件映射。
3. 若新源哈希仍不符，返回报告继续调查数值环境与滤波系数，不修改冻结记录、不读取目标性能决定方案。冻结数组只有哈希时无法推导逐数值误差，应明确缺少数值参考，不能捏造差异幅度。
4. 新重建匹配可证明新平台满足既有输入身份；不能单独解释旧失败原因。父对话审阅后，为同一未开始实验建立明确关联旧0-fit失败的补充执行/迁移登记，保留原预算账本，并将用户最新预算授权写成追加记录。现有机器/版本/截止门控仍在；此次不实现或执行清零预算、跨机器自动续跑。
5. R2实际完整读回与条件写入/CAS能力必须先验证；SDK支持相应参数已离线确认，真实R2兼容性和权限尚未验证。存在安全注入的GH写权限也须按原方案验证。全套门控完成后，父对话才统一安排论文1占用GPU。

## 未来训练环境（本轮不执行）

`PREPARE_TRAINING_ENV.sh /workspace/mi-eeg-cloud/runtime-reviewed-r2` 先要求host精确torch2.8.0+cu128，仅创建新的带system-site只读继承的venv；通过局部site-packages覆盖numpy等，不修改host或论文2环境。只装torchaudio2.8.0轮子及锁定生产依赖，用torch/torchaudio约束防止升级/重新下载整套Torch；准备前至少12GiB空闲，完成后至少10GiB，失败不继续。现有环境不覆盖。该GPU环境方案仅语法检查，当前Codex无匹配host，不能声称RunPod已安装验证。原launcher会重新验证全部固定生产包、CUDA可用性与实际CUDA算术。

实际训练只使用 `LAUNCH_R2_ONLY.sh`，它要求已审核完整R2映射路径及SHA、既有安全GH/R2绑定，设置无cache/无prompt凭据模式并强制R2备份。这是未来执行入口，不是当前训练放行命令。旧launcher文件保留兼容回归；当前prepare及trainer自身也严格要求R2导入及私有恢复。新实际代码版本要重新公开冻结，不可套用旧05e683e9任务的注册。

## 人工审阅恢复与关机

```bash
python scripts/private_recovery.py restore-review-copy --job-id <原job-id> --destination <全新审核目录>
python scripts/private_recovery.py backup-stopped-worker-log --job-dir <已停止worker的job目录>
```

上述命令从 `REDESIGN_CLOUD_20261013` 目录运行，使用既有R2绑定；restore成功仅是 `VERIFIED_REVIEW_COPY_NOT_RESUME_AUTHORIZATION`。目录内含work_root子目录的原登记/预算副本，但工具从不安装这些副本或修改机器锁。PENDING状态需保留现场并人工核实；丢失未提交更新无法证明时不重跑。备份未确认时不得计划Stop；若外部故障已导致丢失，明确报告未知更新而不将旧快照冒充最新状态。
