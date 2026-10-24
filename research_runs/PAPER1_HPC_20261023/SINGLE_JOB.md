# 学校HPC：登录端下载与同步，一个节点内两卡并行

当前正式入口为 `RUN_SINGLE_JOB_ON_SCHOOL.sh`，采用 **一个Slurm作业、一个节点、2GPU、总26CPU、总128G内存**。两个独立训练进程各对应13CPU；节点内存由作业共享，不是每卡再申请128G。Slurm负责GPU分配，worker使用自己的`cuda:0`。这是独立方法/种子/折数并行，不是同一个模型的DDP。

## 已观察的问题及修复

2026-10-24学校日志证明：771084曾在gpu2启动，第一份BNCI下载遇`gaierror -2`，四次尝试后退出1；该次作业没有进入训练。随后用户在login1对同一TU Graz官方文件的HEAD获得200及冻结大小43772146。名称解析错误可能涉及目标或代理路径，不能据此声称所有计算节点都没有外网。用户已明确允许login1用一个后台进程进行数据下载，解压、EEG预处理及训练仍留在计算节点。

当前流程：

1. 在login1隐藏输入GitHub Contents读写token，真正写入`connection.json`，按写入commit回读并核对字节、大小及Git blob SHA。终端必须显示`CONTENTS_WRITE_READBACK_VERIFIED`；本地缓存或`INITIAL_WRITE_PENDING`不能替代这项确认。token通过stdin交给IPv4 curl，只在验证成功后替换私有缓存，不写入Git、参数或日志。
2. 独立后台下载器在login1恢复18个BNCI、174个Dreyer原始对象及312个Yang压缩成员。登录端不解压Yang、不导入EEG、不训练。原始文件、固定大小/SHA、TLS和窄跳转规则不变；已有文件和partial复用。网络临时错误按有界退避恢复同一下载；哈希、磁盘或数据规则错误保留现场并明确报告。
3. 登录端GitHub同步器每约180秒上传下载阶段、已完成对象数、真实训练step和统计摘要。它与下载及模型训练分离；网络/限流失败不会终止模型训练。
4. 所有网络载荷完整后，自动提交唯一的离线GPU作业，申请`hpc_gpu`的`gpu:2`、26CPU、128G。共享目录保存原始文件、压缩缓存和断点；计算节点只从这些文件恢复，不再通过HTTP下载。
5. 计算节点逐成员解压Yang，核验原CRC及SHA后才发布原始文件，然后逐人预处理。只在原始及输入校验通过后进行GPU小检查、75项开发训练、15项最终训练及外部评价。已完成的人员、任务、epoch/step和评价分片继续复用。

## 一行启动与恢复

在login1完整执行：

```bash
curl -4 -f --connect-timeout 8 --max-time 60 --retry 1 -H 'Accept: application/vnd.github.raw+json' 'https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg/contents/research_runs/PAPER1_HPC_20261023/RUN_SINGLE_JOB_ON_SCHOOL.sh?ref=main' -o /tmp/paper1-start.sh && bash /tmp/paper1-start.sh --reauthorize --gpus 2 --memory 128G --replace-job 771084
```

代码包和固定wheel通过GitHub官方API在login1准备/复用。计算作业不下载代码或依赖，不修改共享Paper3环境。原安装锁文件和旧失败记录保留；新的代码更新锁在出现授权提示前释放，关闭输入窗口不会继续占用代码更新锁。

若仅需继续已经配置好的流程：

```bash
bash ~/projects/PAPER1_HPC_20261023/LAUNCH.sh --gpus 2 --memory 128G
```

需要重新输入token时追加`--reauthorize`。同项目正在运行的下载器、同步器及Slurm作业会被识别并复用，不重复启动fit。后台下载器已被真实PID/状态观察后可关闭终端；进程脱离终端，stdin关闭，日志写共享目录。普通续跑不会重跑整套测试、全量原始SHA或额外科研pilot。

## 旧作业替换

`--replace-job 771084`不会直接盲目取消作业。先验证GitHub和网络载荷，再核对真实队列。若旧ID已离开队列，保留其历史记录，提交新作业，不虚构其终态。若旧作业仍PENDING，先创建held后继并核实新ID、用户、项目和队列身份，再仅以`scancel --state=PENDING`取消确切旧ID，确认其离开队列后释放后继。新提交失败时旧作业保留。若旧作业已RUNNING/COMPLETING，保留旧作业和held后继，避免两个进程修改同一研究输出；不会声称新训练已经正常。其它论文及作业不参与此替换。短暂held后继可能计入学校作业数量上限；若调度器拒绝，旧作业仍保留。

## 查看实际状态

```bash
cat ~/projects/paper1-risk-v1/state/login_pipeline_status.json
```

```bash
tail -n 30 ~/projects/paper1-risk-v1/logs/login-pipeline.log
```

GPU作业的主日志为`logs/slurm/single-<jobid>.out`；训练任务日志为`logs/workers/<task_id>.log`。同步状态为`state/github_sync_status.json`，同步日志为`logs/github-sync-login.log`。GitHub进度分支为`hpc/paper1-risk-v1`，文件为`hpc_status/paper1-risk-v1/status.json`。

`LOGIN_TRANSFER_PIPELINE_STARTED`只证明登录后台启动，`SINGLE_JOB_SUBMITTED`只证明调度器接受，排队时界面显示0核并不代表节点没有CPU。只有实际stage、optimizer_updates及checkpoint增长才能证明训练推进。一次HEAD成功也不等于全部数据下载完成。

## 中断和科学边界

checkpoint保留模型、优化器、调度器、随机状态、采样位置、最佳模型及验证历史，按耗时保存两代；USR1转发实际worker，等待保存后只重排当前作业。用户主动取消不自动复活。独立fit失败不取消其它fit；已有错误、checkpoint及负/零结果保持。

本次只修复运输、授权、资源分配和恢复机制。冻结方法、种子、人员分组、trial范围、损失、滤波、输入身份和统计计划不变。尚未在学校替用户执行新入口，也未把合成测试当作新科研fit或正式GPU验收。
