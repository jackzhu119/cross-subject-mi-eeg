# 论文1：学校HPC运行与新算法研究

**当前入口：** [SINGLE_JOB.md](SINGLE_JOB.md) · [官方隐私修正版数据来源](NEMAR_PRIVACY_SOURCE.md) · [研究协议](PROJECT_PROTOCOL.md)

本目录提供学校服务器上的数据恢复、离线预处理、训练、断点续跑与GitHub进度同步。后续算法研究与[已完成eligible-v3结果](../ELIGIBLE_V3_RESULTS_20261018/README_zh.md)分别记录，论文候选稿见[仓库首页](../../README.md)。本页更新于2026-10-25；原始目录和旧实验保持。

## 当前运行配置

| 项目 | 配置 |
|---|---|
| 学校账号／登录节点 | `zhuziyuan`／`login1` |
| 分区／作业形态 | `hpc_gpu`；**一个作业、一个节点** |
| GPU／CPU／内存总量 | **2GPU／24核CPU／128G**；最多两个单卡worker，各对应12CPU |
| 代码目录 | `/public/home/zhuziyuan/projects/PAPER1_HPC_20261023` |
| 持久项目目录 | `/public/home/zhuziyuan/projects/paper1-risk-v1` |
| 当前GPU解释器 | `/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python` |
| CPU预处理 | 项目内独立NumPy2.2.6／SciPy1.15.3环境；不修改共享GPU环境 |
| 下载与进度 | login1后台下载；独立GitHub同步约180秒一次 |

Slurm分配GPU；不硬编码物理设备或旧UUID。两张卡分别执行独立任务，并非同步DDP。上表是实际单作业入口的总资源；旧基础配置或历史数组脚本不能替代当前提交器的设置。

## 一行下载、启动或恢复

在 **login1** 完整执行：

```bash
curl -4 -f --connect-timeout 8 --max-time 60 --retry 1 -H 'Accept: application/vnd.github.raw+json' 'https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg/contents/research_runs/PAPER1_HPC_20261023/RUN_SINGLE_JOB_ON_SCHOOL.sh?ref=35de24466aec5ccee809b4e00e67b3949f60297b' -o /tmp/paper1-direct.sh && bash /tmp/paper1-direct.sh --yang-source nemar-privacy-v1 --restart-transfer --gpus 2 --memory 128G --replace-job 771084
```

这是现有`paper1-risk-v1`项目的固定恢复入口，`771084`是其旧作业记录，不可替换为其它论文作业。已有同项目作业会按真实队列状态处理；命令不会直接取消运行中的模型。完整替换规则见[SINGLE_JOB.md](SINGLE_JOB.md)。

入口复用固定代码包，验证GitHub写入与回读后，在login1后台下载。BNCI和Dreyer复用已有文件、partial和回执；Yang采用用户已批准的NEMAR官方隐私修正版，保存到独立输入目录。所有必需文件校验齐备后，自动提交唯一离线计算作业，逐人预处理，再推进训练与评价。无需R2或个人电脑中转。

首次或授权失效时，在终端隐藏输入有仓库Contents读写权限的GitHub token；需要主动更换时追加`--reauthorize`。凭据不写入代码、Git、命令参数或公开日志。

## 下载与恢复

- [独立输入清单、原SHA祖先与当前新SHA](config/yang_nemar_privacy_v1.json)：306份BDF及6份元数据；不将修正版冒充原字节。
- [官方来源与独立核验范围](NEMAR_PRIVACY_SOURCE.md)：完整记录头、事件规则及整文件对照的实际范围。
- [原始数据下载目录](DOWNLOAD_ENTRIES.md)：原冻结清单保留，隐私版须用其单独清单。

数据齐备后才开始科学预处理和拟合。临时网络故障退避重试，完成文件复用；SHA、长度或数据规则错误会保留现场并报告。原始数据约71.34GB，另需准备缓存、模型与日志空间，详见[文件保留规则](../../docs/REPOSITORY_GUIDE.md)。

训练按耗时保存两代checkpoint，包含模型、优化器、采样位置、随机状态、最佳模型和验证历史；评价按会话保存。USR1转发worker，实际保存后退出75并尝试requeue；学校不允许自动重排时，同一入口手动续跑。用户主动取消不自动复活。操作修复尽量复用原进度，科学输入或算法版本不能混用checkpoint。

## 查看真实进度

```bash
cat /public/home/zhuziyuan/projects/paper1-risk-v1/state/login_pipeline_status.json
```

```bash
tail -n 40 /public/home/zhuziyuan/projects/paper1-risk-v1/logs/login-pipeline.log
```

| 位置 | 内容 |
|---|---|
| `state/login_pipeline_status.json` | 登录端阶段、下载器PID与提交记录 |
| `raw-nemar-privacy-v1/transport_status.json` | 当前输入版本的完成对象数与分数据集进度 |
| `logs/slurm/single-<jobid>.out` | 单作业阶段、主机、实际进程与退出记录 |
| `logs/workers/<task_id>.log` | 各任务训练日志 |
| `outputs/runs/<task_id>/` | 两代checkpoint、最佳模型、逐会话评价与完成记录 |
| `outputs/analysis/` | 已完成的统计摘要 |
| `state/github_sync_status.json`／`logs/github-sync-login.log` | 独立同步状态与错误恢复 |

GitHub状态见[`hpc/paper1-risk-v1`](https://github.com/jackzhu119/cross-subject-mi-eeg/tree/hpc/paper1-risk-v1)。请核对各字段自己的时间戳；旧作业失败记录可能与新的下载状态同时存在。路线探测、下载完成、Slurm接受和实际模型更新分别判断。同步摘要不等于完整模型备份。

## 研究设计与证据

| 内容 | 文档 |
|---|---|
| 源被试×类别尾部风险、频带一致性及固定基线 | [PROJECT_PROTOCOL.md](PROJECT_PROTOCOL.md) |
| 文献依据与待检验贡献 | [LITERATURE_AND_NOVELTY.md](LITERATURE_AND_NOVELTY.md) |
| 主终点、次比较与统计规则 | [ANALYSIS_PLAN.md](ANALYSIS_PLAN.md) |
| 新Methods草稿 | [MANUSCRIPT_EXTENSION.md](MANUSCRIPT_EXTENSION.md) |
| 隐私版接入与运行测试记录 | [集成核验](evidence/privacy_source_integration_validation_20261025.json) · [固定交付](evidence/privacy_source_fixed_delivery_20261025.json) |

研究计划包含75项开发任务与15项最终任务，共90项；这些是计划数量，实际完成情况以任务记录为准。外部Dreyer评价沿用探索性边界，目标数据不参与模型选择或参数拟合。

历史RunPod方案、旧R2恢复记录及初版数组流程保留各自版本；当前操作以本页和`SINGLE_JOB.md`为准。[整理前HPC说明快照](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/35de24466aec5ccee809b4e00e67b3949f60297b/research_runs/PAPER1_HPC_20261023/README_zh.md)保留了此前的操作说明。
