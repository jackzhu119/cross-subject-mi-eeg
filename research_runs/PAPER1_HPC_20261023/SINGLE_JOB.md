# 学校HPC：完整流程只占一个Slurm作业

当前入口把下载、原始预处理、GPU小检查、全部训练、评价、统计及GitHub同步放进同一个Slurm作业。作业申请 `hpc_gpu` 分区的 **2张GPU、32核CPU、256G内存**，相当于每卡16核/128G；内部最多两个独立单卡训练进程。不会继续创建数组、单独预处理作业或其它训练子作业。

在 `login1` 执行下面这一整行：

```bash
curl -fL --connect-timeout 20 --retry 3 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/main/research_runs/PAPER1_HPC_20261023/RUN_SINGLE_JOB_ON_SCHOOL.sh -o /tmp/paper1-single-job.sh && bash /tmp/paper1-single-job.sh
```

入口为 `RUN_SINGLE_JOB_ON_SCHOOL.sh`。它先复用现有53MB离线包，安装一个很小且固定SHA的运行层补丁，再一次性准备/复用项目CPU预处理环境。旧共享Torch环境保持原样。首次会隐藏提示输入新的GitHub Contents读写token，私有保存后不必每次输入；不要把token粘贴到聊天或写入公开脚本。

已在运行或排队的同项目单作业会复用。身份核对通过的旧PENDING下载作业会保留原记录后取消，再提交新单作业；运行中的旧下载或旧训练会保留，并明确告知当前没有创建第二个作业。其它论文和作业不受这些操作影响。

旧失败日志 `download-770688.err` 等保留。2026-10-24这次失败的根因尚未从旧日志识别；旧程序隐藏了网络及磁盘底层异常。修订后下载错误会在主作业日志打印受控JSON，包括阶段、文件、重试次数、偏移、异常类别、errno、HTTP状态、SSL验证代码。签名URL、代理、响应body和密钥不会打印。重试次数仍有界，文件大小及SHA规则保持。仅当BNCI入口发生可识别的DNS、超时、连接或SSL异常时，可尝试已核实的同名TU Graz官方MAT地址；HTTP拒绝、代理拒绝字符串及未知主机不会触发这个备用连接。此传输修订不改变原始文件字节身份。

我方环境已完整下载首个源文件A01E.mat并核验固定SHA；这是我方网络的测试，不能替代学校网络验证。若学校没有计算节点外网，新日志会显示实际DNS/连接/SSL错误；本代码不会绕过网络策略或关闭TLS。

主日志统一为：

```text
/public/home/zhuziyuan/projects/paper1-risk-v1/logs/slurm/single-<作业ID>.out
```

标准错误也写入这一个文件，重排队采用append保存历史。各训练任务的完整日志另存 `logs/workers/<task_id>.log`。轻量状态为 `state/single_job_status.json`，GitHub每约180秒同步阶段和实际step/统计摘要。

一个作业内部的顺序为：

1. 复用已验证原始文件，续传未完成文件。
2. 逐人复用预处理缓存与数据导入记录。
3. 在分配的两个GPU槽分别进行合成前向/反向/保存/恢复小检查，匹配的成功记录会复用。
4. 执行同一研究计划的75项开发训练，最多两项同时运行。
5. 根据源内验证固定选轮，执行15项最终训练及探索性外评。
6. 从已保存评价生成完整统计并同步GitHub。

这只是执行方式变化；方法、种子、人员分组、trial范围、损失、输入哈希及统计计划没有改变。不会把诊断或QA更新计入科研fit。

同一 `RUN_SINGLE_JOB_ON_SCHOOL.sh` 命令可用于恢复；完成任务跳过，未完成任务从原断点继续，评价从会话分片继续。USR1由外壳转发给监督进程，再转发实际worker；等待保存退出75后仅重排当前一个job。用户取消不会自动重新提交。单项失败不取消其它独立fit，同次运行不无限重试；最终保留未完成列表，供同命令手动恢复。

把全过程合在一个作业内意味着下载和CPU预处理期间也会保留两张GPU分配；这满足本次减少作业数量的要求。
