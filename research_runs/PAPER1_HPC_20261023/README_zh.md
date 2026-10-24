# 论文1：学校 HPC 新算法实验运行包

> **学校Figshare入口访问被拒绝**：学校Python和系统curl均已确认入口HTTP403，尚未跳转S3，不能将其当作签名过期或仅Python兼容问题。BNCI缓存和已完成的Dreyer文件保留；新训练等待Yang完整。现有授权备份通路本次只读查询也返回401，未重试。具体网络支持文本及同字节恢复方式见 [YANG_403_STATUS.md](YANG_403_STATUS.md)；当前无需重装或重复跑诊断。

> **2026-10-24 Yang下载修订**：已改为官方GET Range机制，支持两个同文件官方入口、过期链接刷新和独立数据集续传；保留原18个BNCI文件。直接执行SINGLE_JOB.md中的最新固定入口，不修改vendor或科学输入。

> **2026-10-24联网与资源修订**：当前使用 [SINGLE_JOB.md](SINGLE_JOB.md)。login1后台只下载及同步，计算节点离线解压、预处理与训练。唯一Slurm作业申请一个节点、2GPU、总24CPU、总128G；每卡对应12CPU。入口可强制重新输入token并实际写入、回读验证。下文旧独立下载/数组说明保留为历史，当前资源和命令以SINGLE_JOB.md为准。

本版本在已有 eligible-v3 数据定义上，研究**源被试×类别的尾部风险控制与频带一致性**。它是一套待执行的新实验，不把旧论文结果当作新算法的验证结果。原论文、Q1–Q16、历史失败和投稿材料保持原样。

## 固定实验与资源

| 项目 | 本版本设置 |
|---|---|
| 方法 | ERM、GroupDRO、尾部风险、频带一致性、二者组合 |
| 源数据 | BNCI 9人/2,592试次＋Yang 51人/30,591试次 |
| 外部数据 | Dreyer 85人/6,800试次；既往暴露不确定，按探索性外评报告 |
| 开发 | 5个人员外层折×5方法×3种子＝75个任务；每折另有源内验证人员 |
| 最终训练 | 5方法×3独立种子＝15个任务；合计90个新训练任务 |
| 公平比较 | 相同18通道、三视图计算/BN暴露、模型容量、40轮×128更新；固定40轮外评与源内选轮外评分开 |
| 资源 | `hpc_gpu` 分区；1个Slurm作业、1个节点、2GPU、总24CPU、总128G；最多2个单卡worker并行 |
| 主终点 | 源外层人员的较弱类别召回率；先在人员内平均种子，再按队列等权汇总 |
| 次分析 | 四项次比较Holm校正、人员配对置信区间、两种完整外评；输出全部方向的结果 |

方法依据及可检验贡献见 [PROJECT_PROTOCOL.md](PROJECT_PROTOCOL.md)、[LITERATURE_AND_NOVELTY.md](LITERATURE_AND_NOVELTY.md)、[ANALYSIS_PLAN.md](ANALYSIS_PLAN.md)。新Methods草稿见 [MANUSCRIPT_EXTENSION.md](MANUSCRIPT_EXTENSION.md)。现在没有新算法效果数据，不预先承诺优于基线。

## 从完全没有数据开始

**可以直接在学校服务器下载，不需要经过本地电脑。** 在 `login1` 执行下面这一行：

```bash
curl -4 -f --connect-timeout 8 --max-time 60 --retry 1 -H 'Accept: application/vnd.github.raw+json' 'https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg/contents/research_runs/PAPER1_HPC_20261023/RUN_SINGLE_JOB_ON_SCHOOL.sh?ref=main' -o /tmp/paper1-single-job.sh && bash /tmp/paper1-single-job.sh
```

这个入口在登录节点复用或下载约53MB固定运行包、核对SHA256并解压，隐藏输入GitHub token并验证远端写入及回读。随后由login1后台恢复原始网络载荷，全部就绪后自动提交一个Slurm作业（`hpc_gpu`分区，1节点、总2GPU/24CPU/128G），在计算节点离线解压、预处理、两卡训练及评价。GitHub进度同步独立在登录端运行。数据直接保存到 `/public/home/zhuziyuan/projects/paper1-risk-v1/raw`。重复同命令会复用包、正在运行的同项目作业、原始文件和训练断点。后续独立下载/数组流程是初版记录，当前采用 [SINGLE_JOB.md](SINGLE_JOB.md)。

2026-10-24资源修订：入口会将已解压包和已存在项目的两份 `config/cluster.json` 同步改为 `partition=hpc_gpu`、`gres=gpu:1`、`exclude=[]`、`cpus_per_task=12`、`max_parallel=2`，保留旧配置。12CPU是单worker对应值，最终唯一作业申请总24CPU、2GPU、128G。旧离线包及其原始manifest仍保留原source身份，此处属于资源操作覆盖；Slurm分配GPU，不硬编码物理编号或旧UUID。

## 历史手动下载与数组流程（当前入口不执行）

若同一项目的旧下载作业仍在 `hpc_gpu1` 排队，入口核对作业名、用户、工作目录及状态后，先保存旧记录和脚本，再以 `scancel --state=PENDING` 取消排队项并在新分区重提。若作业已变为运行状态，则保留它，不启动第二个下载。示例截图中的770682属于待现场核对的作业，不表示本助手已操作它。

日志位于 `/public/home/zhuziyuan/projects/paper1-risk-v1/logs/slurm/download-<jobid>.out` 和 `.err`。看到 `ALL_RAW_DATASETS_READY` 后，回到 `login1` 执行本文的LAUNCH命令进入训练，首次隐藏输入GitHub token。下载公开运行包和数据本身不需要GitHub、R2或RunPod密钥。

学校计算节点的外网访问尚未现场观察。若作业报告DNS/连接超时，应根据真实日志确认学校网络；不能把本环境的访问成功当成学校已验证。训练代码和数据校验规则不因此改变。

也可以采用下面的手动下载/解压方式：

下载发布附件 `paper1-hpc-offline.tar.gz` 和同名 `.sha256`。压缩包包含本目录代码、固定数据清单和两份CPU预处理wheel，不含EEG、GitHub token或旧模型。先校验压缩包，再解压到项目父目录。

```bash
sha256sum -c paper1-hpc-offline.tar.gz.sha256
```

```bash
tar -xzf paper1-hpc-offline.tar.gz -C /public/home/zhuziyuan/projects
```

**先下载数据，再启动计算。** 在允许联网和大文件传输的Linux机器/学校数据传输节点执行下面这一行。不要在限制为轻量提交用途的 `login1` 上进行68GB解压；若只能在校外下载，把完整 `raw` 目录连同隐藏的校验记录一次上传到下列学校路径。学校的节点联网政策尚未现场核实。

```bash
bash /public/home/zhuziyuan/projects/PAPER1_HPC_20261023/FETCH_DATA.sh --raw-dir /public/home/zhuziyuan/projects/paper1-risk-v1/raw
```

在校外机器可把上面两个绝对路径换成本机实际路径。`FETCH_DATA.sh`只需Python 3标准库，可通过 `PAPER1_FETCH_PYTHON` 指定解释器。BNCI、Yang、Dreyer分开保存；断网后执行**同一条命令**，已验证文件不重下，未完成文件续传。需单独补某个数据集时追加 `--dataset bnci`、`--dataset yang` 或 `--dataset dreyer`。

原始文件总量约71.34GB（十进制），另需预处理NPZ、NPY、断点及日志空间，建议项目可用空间至少 **100GiB**。这不是已核实的学校配额。Yang采用官方v5 ZIP的分成员Range下载，避免下载不使用的其他部分。所有306个Yang信号/事件文件均对照固定SHA256；另外6个元数据文件校验固定目录CRC并记录SHA。BNCI18个MAT和Dreyer174个EDF校验固定大小和SHA。全部校验完成才生成可供离线计算的清单。

下载使用HTTPS。BNCI官方入口当前跳转至其TU Graz数据路径；Dreyer仅接受已核实NEMAR存储主机的精确对象。代码处理这些具体跳转，不要求用户手动复制签名链接。401/403、大小或哈希不匹配会保留文件并明确报错。

下载机制和合成续传测试已经检查；本环境的官方URL HEAD及Yang远程ZIP目录Range校验记录在 `evidence/public_download_metadata.json` 和 `evidence/yang_live_metadata.json`。**尚未在学校网络完成全部约71GB下载，不能把HEAD成功当成全文件下载通过。**

## 一行启动，也是一行续跑

数据已放到上述学校路径后，在 `login1` 执行：

```bash
bash /public/home/zhuziyuan/projects/PAPER1_HPC_20261023/LAUNCH.sh
```

首次启动会隐藏提示输入 **GitHub token**，必须对 `jackzhu119/cross-subject-mi-eeg` 具有 Contents读写权限。token仅保存在本人的 `~/.config/mi-eeg/` 私有目录，文件权限600，不写入项目、日志或Git。首次会尝试写入独立状态分支验证权限；明确401/403需修正授权，临时网络故障则保留待同步状态。已授权项目续跑不重复输入，后台每约180秒自动推送。已贴到聊天或公开页面的token应撤销，替换后的值只在学校终端隐藏输入。

默认训练解释器是已存在的：
`/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python`。
启动只读核对Python3.12.3、Torch2.5.1+cu121、NumPy2.2.6；不修改这个环境。原始预处理用项目内独立CPU环境 `.venvs/preprocessing-cp312`，从离线包安装固定NumPy2.2.6/SciPy1.15.3，不安装另一套CUDA。

启动链路为：

1. 一个单卡配额的预处理作业（实际只用CPU），逐人保存并复用输出。
2. 一个GPU合成小检查：前向、反向、保存、恢复；同配置成功后复用。
3. 75项开发数组，每项单卡、最多两项同时运行。
4. 开发完成后，仅依据源内验证选轮，自动追加15项最终训练和外评。
5. 从已保存评价计算统计摘要并推送GitHub。

预处理也按 `hpc_gpu` 的单卡、16CPU、128G配额提交，实际仅执行CPU预处理，完成后释放配额。随后训练数组最多两项同时运行。

其它路径示例：

```bash
bash /public/home/zhuziyuan/projects/PAPER1_HPC_20261023/LAUNCH.sh --project /public/home/zhuziyuan/projects/paper1-risk-v1 --raw-dir /实际/raw目录
```

项目首次创建后，科学配置和输入身份固定。后续同命令直接复用，不再全量pytest、试训或扫描原始数据SHA。操作参数在项目 `config/cluster.json`；当前新分区不指定节点名或GPU型号，旧分区的gpu3异常记录保留。单项Slurm time默认1天，可按学校实际上限调整；没有人为累计12小时限制。

## 中断、取消与失败

每180秒或每轮结束保存一次两代断点，包含模型、Adam状态、调度器/AMP状态（当前未启用）、轮次/更新步、采样器/RNG、GroupDRO权重、最佳模型和历史。评价按人/会话保存。数据/算法改变需要另一个实验版本；运行层修复尽量继续原断点。

Slurm提前USR1会转发给Python，真实保存并退出75后才尝试一次 `scontrol requeue`。学校拒绝requeue时，重新执行同一条LAUNCH即可。用户取消时不自动复活。某项报错不取消其它独立数组项；失败任务待用户同命令续跑，仅补未完成任务。已存在运行中的数组不会再重复提交。

两代断点都损坏或实际更新后丢失断点时会保留错误，不会默默从0重训。GPU UUID不是恢复条件；跨软件/设备逐位一致性不作无证据保证，实际运行版本写入历史。

## 进度和输出

```bash
cat /public/home/zhuziyuan/projects/paper1-risk-v1/state/controller_status.json
```

```bash
bash /public/home/zhuziyuan/projects/PAPER1_HPC_20261023/STATUS.sh
```

| 路径（项目内） | 内容 |
|---|---|
| `logs/slurm/` | 任务/主机/时间、实际step、traceback、退出码 |
| `outputs/runs/<任务>/` | 两代断点、最佳模型、逐会话评价、完成记录 |
| `outputs/analysis/` | 全方法、全方向的人员级汇总和统计 |
| `state/submissions.json` | Slurm任务身份和历史 |
| `logs/github-sync.log` | 每约180秒独立同步；网络错误自动退避重试 |
| `logs/controller.log` | 自动阶段推进，不进行模型训练 |

GitHub状态分支为 `hpc/paper1-risk-v1`，文件为 `hpc_status/paper1-risk-v1/status.json`，不会改投稿主文。同步的是进度与统计摘要，**不是模型/原始EEG备份**；全部权重和完整评价保存在 `/public/home`。网络或GitHub限流不会中断训练。

轻量控制器/同步器以独立进程运行；关闭终端不会发送挂断给它们。若学校登录节点清理后台进程，训练数组仍在Slurm中继续，同一LAUNCH会恢复监控和后续阶段。不要把Slurm RUNNING或心跳时间本身当作参数已更新；看任务的 `global_step`、`optimizer_updates` 与断点时间。

## 验证范围

本地已做目标Torch2.5.1 API的CPU合成训练/断点测试、Slurm模拟与真实Bash信号测试、下载/哈希/断点测试、独立预处理环境离线安装及数值小检查。没有连接学校集群、运行真实EEG训练或宣称新算法已取得阳性结果。最终测试清单见 `evidence/VALIDATION.md`。
