# 学校HPC：登录端下载与同步，一个节点内两卡并行

当前正式入口为 `RUN_SINGLE_JOB_ON_SCHOOL.sh`，采用 **一个Slurm作业、一个节点、2GPU、总24CPU、总128G内存**。两个独立训练进程各对应12CPU；节点内存由作业共享，不是每卡再申请128G。Slurm负责GPU分配，worker使用自己的`cuda:0`。这是独立方法/种子/折数并行，不是同一个模型的DDP。

**2026-10-25已获用户明确批准的直接下载修订：** 使用 `--yang-source nemar-privacy-v1` 从NEMAR官方取得隐私修正版Yang原生文件，避开学校已实测403的Figshare入口；不依赖R2。新文件按独立固定SHA和时钟/事件清单核验，原清单、旧结果及失败不变。现有BNCI/Dreyer下载和partial直接复用。详见 [来源、独立核验与版本边界](NEMAR_PRIVACY_SOURCE.md)。以下历史Figshare压缩运输说明仍适用于未选择该新版本的原流程；新版本在登录端直接取得完整原生文件，计算节点无需解压Yang。

## 已观察的问题及修复

2026-10-24学校日志证明：771084曾在gpu2启动，第一份BNCI下载遇`gaierror -2`，四次尝试后退出1；该次作业没有进入训练。随后用户在login1对同一TU Graz官方文件的HEAD获得200及冻结大小43772146。名称解析错误可能涉及目标或代理路径，不能据此声称所有计算节点都没有外网。用户已明确允许login1用一个后台进程进行数据下载，解压、EEG预处理及训练仍留在计算节点。

当前流程：

1. 在login1隐藏输入GitHub Contents读写token，真正写入`connection.json`，按写入commit回读并核对字节、大小及Git blob SHA。终端必须显示`CONTENTS_WRITE_READBACK_VERIFIED`；本地缓存或`INITIAL_WRITE_PENDING`不能替代这项确认。token通过stdin交给IPv4 curl，只在验证成功后替换私有缓存，不写入Git、参数或日志。
2. 独立后台下载器在login1恢复18个BNCI、174个Dreyer原始对象及312个Yang压缩成员。登录端不解压Yang、不导入EEG、不训练。原始文件、固定大小/SHA、TLS和窄跳转规则不变；已有文件和partial复用。网络临时错误按有界退避恢复同一下载；哈希、磁盘或数据规则错误保留现场并明确报告。
3. 登录端GitHub同步器每约180秒上传下载阶段、已完成对象数、真实训练step和统计摘要。它与下载及模型训练分离；网络/限流失败不会终止模型训练。
4. 所有网络载荷完整后，自动提交唯一的离线GPU作业，申请`hpc_gpu`的`gpu:2`、24CPU、128G。共享目录保存原始文件、压缩缓存和断点；计算节点只从这些文件恢复，不再通过HTTP下载。
5. 计算节点逐成员解压Yang，核验原CRC及SHA后才发布原始文件，然后逐人预处理。只在原始及输入校验通过后进行GPU小检查、75项开发训练、15项最终训练及外部评价。已完成的人员、任务、epoch/step和评价分片继续复用。

## 一行启动与恢复

在login1完整执行：

```bash
curl -4 -f --connect-timeout 8 --max-time 60 --retry 1 -H 'Accept: application/vnd.github.raw+json' 'https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg/contents/research_runs/PAPER1_HPC_20261023/RUN_SINGLE_JOB_ON_SCHOOL.sh?ref=main' -o /tmp/paper1-start.sh && bash /tmp/paper1-start.sh --yang-source nemar-privacy-v1 --restart-transfer --gpus 2 --memory 128G --replace-job 771084
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

## 2026-10-24：连接错误与下载证书修正

实际登录端日志显示BNCI入口返回`ENETUNREACH(101)`；原代码没有将基础`OSError(101)`归入现有官方备用路径条件。修订后仅对`ENETUNREACH/EHOSTUNREACH/ENETDOWN`这三类明确网络错误尝试原冻结同名TU Graz地址，权限/磁盘/HTTP拒绝不触发该路径。BNCI不可达入口的等待缩为8秒，备用文件读取仍保留原60秒超时。官方地址、大小、SHA和TLS身份验证没有变化。

用户随后在学校的实际Python对TU Graz做HEAD，明确得到`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`，而系统curl对同址返回200。下载子进程现读取已存在的系统CA（优先EL7的`/etc/pki/tls/certs/ca-bundle.crt`等），或尊重显式配置的CA文件/目录。证书和hostname验证始终开启；不修改系统CA、共享Python或其它论文环境。离线发布不加载或检查网络CA。

升级时在上述启动命令中追加`--restart-transfer`，会先用学校实际Python检查未完成数据源：BNCI使用官方HEAD，Yang使用GET Range核对冻结ZIP目录，Dreyer使用1字节GET Range。`DOWNLOAD_SOURCES_PREFLIGHT_VERIFIED`只表示路线与元数据已核对；暂时不可用则记录`DOWNLOAD_SOURCES_RETRY_PENDING`并由后台继续其它独立源。不会将路线探测当作完整数据SHA验证。随后只会重启同用户、同项目、仍处于下载/网络等待阶段的旧登录进程，等待退出后复用原文件和partial；不会终止Slurm模型作业或其它论文。`--reauthorize`可同时要求输入新token。正常下载证据为`bnci ... raw objects verified`和`transport_status.json`完成数增长，而不是只有后台heartbeat。

## 2026-10-24：Yang GET机制与多入口恢复

学校原日志在18个BNCI完成后，于Yang的`HTTPRangeReader._resolve()`使用HEAD时收到403。已对同一个官方签名对象、相同请求头，仅改变HTTP方法进行复现：HEAD403，GET Range206。因此HPC改用专用GET运输适配器，**不修改任何vendor冻结文件**，避免破坏后续科学代码hash验收。

验证过的两条入口是：

- `https://ndownloader.figshare.com/files/51001884`
- `https://api.figshare.com/v2/file/download/51001884`

两者都是Figshare官方入口，指向同一冻结文件及同一个S3后端；不是两份独立镜像。入口网络/临时服务故障时会切换；官方链接明确过期时刷新一次。真实GET权限拒绝不会被伪装成成功或无限换地址重试。签名只在内存中传输，不写入Git或日志。

每次GET均要求206、精确Content-Range及冻结总长度；若返回200而忽略Range，会在读取全包前停止。ZIP目录SHA、1944成员、312个选中成员的记录必须保持；所有306个原生EEG/event文件仍按原SHA核验，其余6个元数据保持CRC规则。完整65.6GB ZIP的MD5没有因分成员下载而被宣称已验证。

传输按数据集隔离：某个源的临时网络故障不再阻止其它源继续；例如Yang暂不可用时Dreyer仍可恢复，完成数按实际对象累计（BNCI+Dreyer完整时为192/504）。已有BNCI文件不重新下载。网络错误保留每次失败证据并退避续传；磁盘/哈希/固定规则错误仍保留现场并明确报告。所有网络载荷齐备后，自动衔接离线发布、原生校验、预处理、单节点2GPU/总24CPU/128G训练及评价。

升级时的元数据预检最多等待90秒；超时只记录路线待重试，随后交给后台下载器恢复，不把预检超时当作数据完整或训练失败。预检发现固定目录/成员不匹配仍立即报错。存储端临时503保留真实HTTP状态并进入现有网络退避，真实403仍停止该源的自动重试。

开发环境已分别通过两入口验证冻结目录，并完成一个Yang事件文件的真实压缩断点续传、离线CRC/SHA和缓存复用，及Dreyer首EDF完整SHA和断点续传；这些不是全部学校数据下载完成的证明。学校端以新日志中的`yang_route_verified`、压缩字节增长、对象完成数、GPU实际step及checkpoint为准。
