# Cross-subject motor-imagery EEG · Paper 1

跨被试运动想象脑电解码：论文、冻结实验结果与学校HPC研究代码。

**Ziyuan Zhu（朱子元）** · College of Artificial Intelligence Medicine, Chongqing Medical University

[ORCID: 0009-0005-1153-4926](https://orcid.org/0009-0005-1153-4926) · zzy2630816871@gmail.com

本仓库分别保存已完成的论文研究和后续算法实验。阅读论文从下表的当前修订稿开始；学校运行使用专用HPC入口。**导航更新：2026-10-25。**

## 快速导航

| 目的 | 入口 |
|---|---|
| 阅读当前论文修订稿 | [主文DOCX](research_runs/PAPER1_REVIEW_20261020/main_manuscript.docx) · [PDF](research_runs/PAPER1_REVIEW_20261020/main_manuscript.pdf) · [Markdown](research_runs/PAPER1_REVIEW_20261020/manuscript_en.md) |
| 下载当前修订材料 | [2026-10-20材料包](research_runs/PAPER1_REVIEW_20261020/Paper1_Reviewed_20261020.zip) · [版本说明](research_runs/PAPER1_REVIEW_20261020/README.md) |
| 查找配套图表、补充数据与投稿材料 | [2026-10-18完整材料目录](research_runs/PAPER1_PLOS_FINAL_20261018/README_zh.md) |
| 核对已完成研究的数值与审计 | [eligible-v3结果与独立核验](research_runs/ELIGIBLE_V3_RESULTS_20261018/README_zh.md) |
| 在学校下载数据、训练或续跑 | [HPC使用说明](research_runs/PAPER1_HPC_20261023/README_zh.md) · [单作业运行流程](research_runs/PAPER1_HPC_20261023/SINGLE_JOB.md) |
| 查看学校任务的已上传进度 | [运行分支](https://github.com/jackzhu119/cross-subject-mi-eeg/tree/hpc/paper1-risk-v1) · [状态JSON](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/hpc/paper1-risk-v1/hpc_status/paper1-risk-v1/status.json) |
| 查找其它版本与历史实验 | [研究目录索引](research_runs/README.md) · [仓库文件指南](docs/REPOSITORY_GUIDE.md) |

## 论文与已完成结果

**Source-cohort expansion improves weaker-class coverage in cross-subject motor-imagery EEG decoding**

该研究比较9、29和60名源参与者配置，包含108条神经网络训练轨迹、9次传统模型拟合，以及85名Dreyer参与者的探索性外部评价。冻结主比较中，S60相对S9的较弱类别召回率提高21.17个百分点，平衡准确率提高5.85个百分点。完整比较、个体差异及统计边界见论文和[冻结结果](research_runs/ELIGIBLE_V3_RESULTS_20261018/RESULTS_REVIEW_zh.md)。

当前论文文件采用 **2026-10-20修订稿**，配套材料按以下组合使用：

| 材料 | 对应文件 |
|---|---|
| 主文、补充方法与投稿信 | [20日修订目录](research_runs/PAPER1_REVIEW_20261020/README.md) |
| 修订Figure 1 | [20日Figure 1文件](research_runs/PAPER1_REVIEW_20261020/figures/) |
| Figures 2–7与表格 | [18日图件](research_runs/PAPER1_PLOS_FINAL_20261018/figures/) · [表格CSV](research_runs/PAPER1_PLOS_FINAL_20261018/tables/) |
| S1–S4补充数据与预测 | [18日完整材料及文件用途](research_runs/PAPER1_PLOS_FINAL_20261018/README_zh.md) |
| 审阅修改与文档核验 | [修改取舍](research_runs/PAPER1_REVIEW_20261020/EDITORIAL_TRIAGE_zh.md) · [核验记录](research_runs/PAPER1_REVIEW_20261020/RELEASE_VALIDATION.json) |
| 结果复现与来源 | [复现说明](research_runs/PAPER1_PLOS_FINAL_20261018/REPRODUCIBILITY.md) · [独立审计](research_runs/ELIGIBLE_V3_RESULTS_20261018/audits/) |

GitHub公开的是材料版本；期刊系统实际上传文件及投稿状态需另行核对。当前HPC算法研究的结果也不自动并入上述论文。

## 学校HPC：直接下载与断点继续

当前配置为 **`hpc_gpu`分区、一个Slurm作业、一个节点、2张GPU、总24核CPU、总128G内存**。两个单卡worker并行处理独立训练任务；数据下载与GitHub同步在login1后台运行，预处理和训练在计算节点执行。

在学校 **login1** 使用已固定的入口：

```bash
curl -4 -f --connect-timeout 8 --max-time 60 --retry 1 -H 'Accept: application/vnd.github.raw+json' 'https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg/contents/research_runs/PAPER1_HPC_20261023/RUN_SINGLE_JOB_ON_SCHOOL.sh?ref=35de24466aec5ccee809b4e00e67b3949f60297b' -o /tmp/paper1-direct.sh && bash /tmp/paper1-direct.sh --yang-source nemar-privacy-v1 --restart-transfer --gpus 2 --memory 128G --replace-job 771084
```

这一命令对应现有学校项目的下载恢复。它复用已验证文件和partial，在数据齐备后自动提交唯一计算作业；训练与评价按保存的断点继续。GitHub授权在终端隐藏输入或复用已验证的私有配置，每约180秒独立同步进度。R2和个人电脑中转均非前提。

- [运行和恢复细节](research_runs/PAPER1_HPC_20261023/SINGLE_JOB.md)
- [官方隐私修正版Yang来源、独立清单及已完成核验](research_runs/PAPER1_HPC_20261023/NEMAR_PRIVACY_SOURCE.md)
- [后续算法研究协议](research_runs/PAPER1_HPC_20261023/PROJECT_PROTOCOL.md) · [统计分析计划](research_runs/PAPER1_HPC_20261023/ANALYSIS_PLAN.md)

学校项目保存于 `/public/home/zhuziyuan/projects/paper1-risk-v1`。下载完成、调度器接受和实际模型更新是不同阶段；请结合状态文件时间、实际step及checkpoint判断进度。上述新算法研究与已完成eligible-v3实验分别记录。

## 数据与复现边界

原始EEG不包含在本Git仓库中。按原提供方条款取得数据，并使用对应研究版本的输入清单：

| 数据 | 官方来源 | 主要使用版本 |
|---|---|---|
| BNCI2014_001 | [BCI Competition IV 2a](https://www.bbci.de/competition/iv/) | 历史Q系列、eligible-v3与HPC研究 |
| Yang | [Figshare+ v5](https://doi.org/10.25452/figshare.plus.22671172.v5) · [NEMAR nm000348](https://doi.org/10.82901/nemar.nm000348) | eligible-v3；HPC显式采用独立隐私修正版清单 |
| Dreyer | [NEMAR nm000250](https://doi.org/10.82901/nemar.nm000250) | eligible-v3及探索性外部评价 |
| PhysioNet、Cho2017、Lee2019 | [早期研究复现说明](research_runs/PLOS_ONE_SUBMISSION/REPRODUCIBILITY.md) | 历史Q14–Q15外部评价 |

隐私修正版使用自己的真实新SHA，原冻结清单和旧结果仍保留。下载回执、科学结果、模型checkpoint与GitHub进度摘要用途不同；进度同步不等于完整模型备份。

## 文件组织

| 目录 | 内容 |
|---|---|
| [research_runs/](research_runs/README.md) | 分版本论文、冻结协议、结果、审计和HPC运行包 |
| [docs/](docs/README.md) | 仓库指南、研究笔记和早期方法记录 |
| [src/mi_eeg/](src/mi_eeg/) · [configs/](configs/) · [tests/](tests/README.md) | 原研究通用代码、配置与测试；HPC代码及依赖在其独立目录 |
| [experiments/](experiments/) · [results/](results/) · [outputs/](outputs/README.md) | 历史实验入口及按实验身份保存的输出 |
| [paper/](paper/README.md) · [references/](references/README.md) | 早期写作提纲与文献资料；当前主文见顶部导航 |

历史目录保留原路径，以维持manifest、hash、审计引用及断点的可追溯性。旧版首页可从[整理前快照](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/35de24466aec5ccee809b4e00e67b3949f60297b/README.md)查看。

## 引用与许可

引用时请注明实际使用的论文版本和科学结果commit；已完成eligible-v3结果的固定交接为 [`040956085499ed788948de0d5a09cddd9eabca56`](https://github.com/jackzhu119/cross-subject-mi-eeg/tree/040956085499ed788948de0d5a09cddd9eabca56/research_runs/ELIGIBLE_V3_RESULTS_20261018/)。

作者自有代码采用 [MIT](LICENSE)；作者自有论文文字、图表及派生研究输出采用 [CC BY 4.0](LICENSE-DATA.md)。原始数据、第三方代码和其它材料遵循其原有条款，详见[许可范围](LICENSING.md)。
