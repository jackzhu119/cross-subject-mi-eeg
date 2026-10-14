# 用户完整执行约束对齐与最小下一步

本轮增量核查：Codex环境可用；开始时工作树干净、无未完成上传；已验证本地没有仍在运行的测试、源诊断或训练进程。远端研究分支仍为eae194514def23e5d1ec6cbb117d4f84fc6f067f，旧失败结果分支仍为d612f0cc2bcca045ff1304bc95a87df76bfd4a82，已交付实现位于独立handoff分支的c802e65709103189becf7e6ff3a55c99a405a7e8。这次没有重跑已通过的347项测试，没有再次R2请求，没有新增实验或重新初始化。

## 状态区分

- 方案/代码/软件测试：R2-only与私有恢复代码完成，347项离线测试通过；21个变更文件已公开逐字节回读。
- 真实新神经网络实验：未开始。旧任务保存状态0 fits/0 optimizer updates；旧现场不可用，根因未知。
- 新Pod输入重建：尚未执行。诊断依赖环境仅在Codex实际验证成功，未声称RunPod已安装。
- 科学结果独立复核、实验结果备份验证：本阶段没有新结果可宣称完成；软件文件回读不等于科研结果备份。
- 云实例停止/计费：本子任务没有云平台实时连接或停机执行证据。此前父对话提供A4500报价计算$0.25/hr+存储$0.004/hr；这只是历史报价，不是实时总费用。由父对话核查当前状态、两篇任务依赖、真实账单与停止回执。
- 投稿：未执行。未改main、旧投稿包、Q1–Q16、发布标签或作者信息。

## 可先执行的最小环境准备（不需要R2凭据）

父对话在新Pod终端执行下列固定版本命令即可；不要求用户复制密钥、不读EEG、不启动GPU计算、不触碰论文2环境。安装只写新建的paper1诊断venv，已有同名venv会拒绝覆盖。

```bash
set -euo pipefail
mkdir -p /workspace/paper1-diagnostic-bootstrap
cd /workspace/paper1-diagnostic-bootstrap
curl -fSsL https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/c802e65709103189becf7e6ff3a55c99a405a7e8/research_runs/REDESIGN_CLOUD_20261013/PREPARE_DIAGNOSTIC_ENV.sh -o PREPARE_DIAGNOSTIC_ENV.sh
curl -fSsL https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/c802e65709103189becf7e6ff3a55c99a405a7e8/research_runs/REDESIGN_CLOUD_20261013/requirements-diagnostic.txt -o requirements-diagnostic.txt
printf '%s\n' \
'b1f2332e89a10b15c6e4167d089c188a3aa8b8b80d6b650cda34c679f280be12  PREPARE_DIAGNOSTIC_ENV.sh' \
'237efccc68ad2f58245dbb6e7b790dbd00100206e4a18a3ab06bda6ccfedb021  requirements-diagnostic.txt' | sha256sum -c -
bash PREPARE_DIAGNOSTIC_ENV.sh /workspace/paper1-diagnostic-runtime
```

应返回 `PINNED_CPU_DIAGNOSTIC_ENV_READY_NO_FITS` 且pip check通过。若同名环境已存在，先核对版本与已保存安装回执，不删除重建。源数据重建命令及基线Git获取要求见R2_RECOVERY_IMPLEMENTATION.md；此处不启动需要R2的下一步。

## 仍缺的R2对象与访问证据

- 源域：已有18个BNCI MAT的历史R2对象映射，source_r2_mapping.json的SHA256为7d5ec2e9ddec16d2be5cb3778037c96dabb6559b8c208ad4cca9923c67407663，离线已与冻结清单核对，779873919 bytes。但历史key不等于当前可访问。
- 目标域：已有174个Dreyer EDF的冻结路径/尺寸/SHA256，共2515343396 bytes；仍缺这174项实际R2 object_key映射。不得猜key、用文件名代替哈希或退回官方重新下载。新清单必须覆盖全192个原始文件并逐项匹配；新源诊断可先只用18项源映射。
- 此前只读list明确401，之后未重试。最新“权限已给出”是执行授权，不是凭据已轮换/绑定已更新的实测证据；须由父对话确认安全连接状态，不能复用聊天中暴露的值。
- 需要R2真实GET验证、备份Put/Get/条件写入能力验证，以及目标冻结输入全量重建。这里没有声称这些已通过。

## 预算差异集中交父对话确认

用户最新“不设上限”与当前论文1代码的硬限制确有差异：总US$10，其中US$2预留、每小时总价<=US$0.75、从首次launcher起算8小时。旧起点2026-10-14T07:07:45.290107Z，对应旧截止15:07:45.290107Z。26个核心fits及34440 optimizer updates是研究范围/计数门控，不随费用授权自动取消。

本轮不修改这些数值，不新建或重置旧预算记录。推荐父对话集中确认并追加记录论文1的新执行时间/费用上限策略与旧0-fit失败的关联；不据此扩大科学设计、不自动套用论文2费用授权。完成确认与版本化补充登记后再实施，仍保留有界超时、检查点和失败止损。R2每batch同步快照的真实耗时/请求费用未测，不保证符合原8小时窗口。

## 科研协议对齐

当前研究题目及Broad/shared、fixed20/mean-loss/mean-rank、19通道、分组、seed和所有输入校验保持不变；不从目标结果调参/归一化/BN更新。Dreyer既往使用不确定，始终探索性，不称独立确认。逐参与者统计、失败和负结果保留；没有把重复trial/session/seed增算为独立人数。

已补读STUDY_DECISION、PRIOR_EXPOSURE_UNCONFIRMED_AMENDMENT和REVISED_MANUSCRIPT；旧工作稿仍含计划/候选资格措辞，执行解释以已发布的探索性修订为准。本轮不把计划改写为完成结果，不更新实验结论，不变更作者信息、不投稿。待真实结果与独立复核回传后再推进论文。

仅负责论文1；论文2的SSH公钥安装、可靠性分析、费用与任务状态交由父对话和论文2任务处理，不在本环境伪称执行。两篇共享实例仍由父对话串行调度。

## 增量：服务器CPU环境安装报告（10:08:49 UTC）

父对话浏览器操作报告：2026-10-14 10:08:26–10:08:49 UTC执行，退出0；固定SHA256校验、pip check和固定版本断言均通过；环境占用319,173,368字节。这更新了前述“RunPod尚未安装”的准备状态，但证据层级仅为父对话操作报告，本Codex任务未直接复查服务器。原始安装日志尚待离机读取及SHA256验证，不称完整备份。结构化记录见 `server_cpu_environment_reported_20261014T100849Z.json`。

无EEG读取、无科学fit、未进行源输入重建，旧失败根因仍未知；全部冻结输入、划分、种子、预算与计数限制保持。下一步补齐原始日志的可靠离机验证，不重装环境、不重复已完成测试。
