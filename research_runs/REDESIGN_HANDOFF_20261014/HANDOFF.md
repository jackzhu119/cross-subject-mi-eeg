# 论文1接手与服务器交接 — 2026-10-14

状态：BLOCKED_BEFORE_TRAINING。此次没有启动外部 GPU、购买资源、下载原始 EEG、创建凭据、修改冻结值或运行科研拟合。父对话调度两篇论文并负责服务器操作及关机。

## 版本与证据

- 核实活动分支 `research/source-selection-redesign-20261012` 头为 `eae194514def23e5d1ec6cbb117d4f84fc6f067f`，包含只读诊断工具。隔离工作树 `/workspace/paper1-redesign`，原工作树仍保留旧投稿版本 `d9a11926076bd348696f6e690078955921dac3f8`。根目录没有 AGENTS.md；工作区 .agents/.codex 为空，项目无适用 .agents/skills。
- 失败结果分支 `redesign/run-20261014T071918Z-exploratory-89b0c07d` 本次读取头 `d612f0cc2bcca045ff1304bc95a87df76bfd4a82`。job_status 确认 0 fits、0 updates、0 target predictions。
- 旧 launch_record 科学版本 `05e683e91e2bb39b977970d04402221761e575d2`，预算起点 `2026-10-14T07:07:45.290107+00:00`，原八小时截止约 15:07:45 UTC。runtime_lock 为 RTX 2000 Ada，NumPy 2.3.5、SciPy 1.17.0、Torch 2.8.0+cu128。
- 当前父对话实测是另一个 A4500 20470 MiB / Python3.12.3 / driver580.159.04，无计算进程；/workspace 是30GB根overlay容器盘而非持久卷。不能自动续跑旧机器任务，也不能在空盘伪造原注册。
- `eae1945` 历史本地重建匹配全部2592试次，不证明旧服务器一致。失败分支未发布 supervisor.log、实际数组哈希或诊断 JSON。CPU指令集、滤波系数等仍是待检假设，不是已证实根因。

## 首先交给服务器的最小步骤

仅执行同目录 `READONLY_SERVER_PROBE.sh /workspace/mi-eeg-cloud`，返回磁盘、设备及旧文件存在性；不启动训练。

若原失败机器及完整旧工作根仍在，才执行下面的固定工具（不适用于当前空白新机器）：

```bash
curl -fSsL https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/eae194514def23e5d1ec6cbb117d4f84fc6f067f/research_runs/REDESIGN_CLOUD_20261013/DIAGNOSE_SOURCE_INPUTS.py -o /tmp/paper1-diagnose.py
printf '%s\n' 'af45a14315ba272c5f6ecf8c0fdac67ae5a393cbc52a060b47e282ec547866fe  /tmp/paper1-diagnose.py' | sha256sum -c -
python3 /tmp/paper1-diagnose.py --work-dir /workspace/mi-eeg-cloud
```

逐行成功后再继续。返回 `<work-root>/diagnostics/<job-id>-source-input-diagnostic.json`。该工具使用已有精确数值环境，检查原始SHA、整体/逐试次哈希、metadata/labels/IDs、SOS系数和CPU特性，0 fits。禁止重置冻结记录、预算或注册；缺失旧数据/运行环境时报告缺失，不伪造诊断现场。

## R2 与数据规模

当前安全注入R2变量存在，但本次仅 list `q15/source-originals/BNCI2014_001/` 返回HTTP401 Unauthorized，详见 r2_readonly_probe.json；未重试或打印密钥。父对话正在安全登录，等待有效连接和实际对象清单。

- BNCI：18 MAT、779,873,919 bytes（0.726 GiB），9人、2会话、2592手部试次。映射及SHA/size见 `research_runs/Q15-PREPARATION/BNCI_R2_SOURCE_RECEIPT_20261003.json`，key格式 `q15/source-originals/BNCI2014_001/<sha256>/<filename>`；与Q8原始清单逐个对照后复用。历史备份回执不等于现在可读。
- Dreyer：174 EDF、2,515,343,396 bytes（2.343 GiB），原始87人，冻结排除A17/A41，保留85人6800试次。manifest在 `REDESIGN_SOURCE_SELECTION_20261012/evidence/dataset_sources/dreyer_nemar_acquisition_edf_manifest.json`；其来源是nm000250 v1.0.5 NEMAR EDF镜像，不冒称原始Zenodo GDF。仓库未找到此集合的R2对象映射，须用新清单对照固定SHA和size，不按文件名猜测。
- 三频带目标float32数组至少496,128,000 bytes（0.462 GiB）；源三频带数组约189,112,320 bytes。原始+目标数组约3.53 GiB，尚不含源数组、Python/CUDA、Git、模型、日志及临时文件。
- 旧启动器的 `--r2` 只备份，数据缺失时仍走官方URL；本轮禁止直接使用。需后续实现并测试仅R2/已验证本地缓存读取且无官方回退。此次未重新下载来源数据。

## 训练方案和启动门槛

设计保持：19通道160Hz、[0.5,2.5)320点，broad/mu/beta；源分组2/2/2/3等fold权重；8条40epoch验证轨迹，固定20/mean-loss/mean-rank，3个冻结seed，18个名义最终单元，共最多26个核心fits（完全同配置可依注册复用），额外40 fits关闭。目标只eval，绝不调参或更新BN。全部结论仅探索性。

A4500显存尺度适合该小模型，但未进行该机真实CUDA算术、固定依赖检查或完整训练，不能报告实测训练耗时。旧启动器最低10GiB空闲只检查启动瞬间，不能证明30GB容器足够。要求安装后重新核算 df 可用空间；为原始/数组/临时数据保留至少6GiB，另保留5GiB运行余量及实测模型/日志预算。关闭pip下载缓存；优先使用已满足2.8.0/cu128的环境，避免双份CUDA安装。超出实测可用空间则阻塞，不自动购买卷。

用户最新无预算上限优先于旧$10限制，但本次不擅自删除旧账本。旧程序仍强制$10/8小时/每小时<=0.75；新机器迁移/预算修订应单独登记保留历史后测试，不能用换目录、清零或改时间绕过。已知当前费用$0.254/hr仅来自父对话，费用从实际开机即累计；两篇串行共用GPU。

## 易失盘备份与失败恢复：启动前必须解决

现有 supervisor 每60秒检查已完成fit数变化并发布已完成checkpoint/曲线到GitHub且回读验证；它明确排除 `resume_state.pt`、`update_intent.json` 和 `supervisor.log`。R2备份只在最终完成阶段调用。因而当前机制不能保证容器丢失后恢复进行中的fit，也不能保证原日志离机保留。

在正式开跑前，应实现并测试：在已提交batch边界暂停写入，将恢复状态/RNG/optimizer、预算账本、更新intent及配置登记形成一致快照；对清理敏感内容后的日志与恢复快照在私有R2版本前缀备份，写manifest(SHA256/size)并完整GET回读验证、最后写commit标记；恢复只接受完整一致快照。仅有ETag或上传成功不能算备份。不把凭据缓存、环境转储或受限原始EEG放入公共GitHub。避免后台复制正在变化的恢复文件。

无备份确认不计划Stop；失败时先保存安全日志、注册、预算和现有checkpoint离机并验证。若容器已丢失、快照不完整或optimizer更新不确定，阻塞自动恢复，不能悄悄重跑已做实验。该备份增强尚未实现，当前不交付可直接训练的启动命令。

完成后依次核查source独立审计→公开模型冻结→target推理验证→统计独立重算→模型/曲线/预测/统计/安全日志离机SHA回读。父对话确认之后才停机。收到真实结果再继续统计图表和论文，保留负结果；投稿另行确认。

## 未完成项

1. 冻结差异诊断：缺旧失败机器的真实输入/诊断；已读GitHub回执但未证明根因。待父对话回传旧诊断或确认旧现场不可用，制定可审计重建比较。
2. R2读取：当前401，已停止该动作；待安全连接恢复和目标对象清单，不索取聊天token。
3. 仅R2读取路径、跨机器恢复与易失盘一致快照尚需实现测试；因此训练启动处于pending，不是已启动或获软件放行。
4. 没有自动审批拒绝；当前是数据访问和证据/实现不足阻塞。

## 本轮验证

316项软件回归测试通过，3条依赖弃用警告；所有原执行包SHA256通过；只读服务器脚本bash语法通过。首次使用云端现有NumPy2.5.3/SciPy1.18.1时315通过、1项精确版本门控失败；随后单独安装NumPy2.3.5/SciPy1.17.0到隔离目录并重跑316通过，没有修改门控。其余宿主依赖并非完整生产锁，Torch为2.14.0+cu130且CUDA不可用；这些是软件fixture结果，不是GPU或真实数据验证。见validation.json及software_tests.txt。
