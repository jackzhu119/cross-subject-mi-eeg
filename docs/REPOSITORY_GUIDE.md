# 仓库导航：论文1、学校HPC与冻结证据

本页按用途整理现有文件，不移动历史目录。论文候选稿、已完成实验与新HPC研究分别保存；运行包更新不代表新训练完成或投稿文件已替换。

## 当前阅读与运行入口

| 用途 | 位置与说明 |
|---|---|
| 学校HPC当前操作 | [SINGLE_JOB.md](../research_runs/PAPER1_HPC_20261023/SINGLE_JOB.md)：`hpc_gpu`，一个Slurm作业、一个节点、2GPU、总24CPU、128G；login1下载，计算节点离线处理与训练 |
| 当前Yang数据恢复 | [NEMAR_PRIVACY_SOURCE.md](../research_runs/PAPER1_HPC_20261023/NEMAR_PRIVACY_SOURCE.md)：用户选择的官方隐私修正版，独立输入身份，复用已有BNCI/Dreyer文件；R2不是前提 |
| HPC研究设计 | [研究协议](../research_runs/PAPER1_HPC_20261023/PROJECT_PROTOCOL.md)与[分析计划](../research_runs/PAPER1_HPC_20261023/ANALYSIS_PLAN.md)：新算法研究的设计依据，不是已有阳性结果 |
| 目前可读论文候选 | [2026-10-20修订说明](../research_runs/PAPER1_REVIEW_20261020/README.md)、[主文源](../research_runs/PAPER1_REVIEW_20261020/manuscript_en.md)、[主文DOCX](../research_runs/PAPER1_REVIEW_20261020/main_manuscript.docx) |
| 配套图表和数据 | [2026-10-18完整论文包](../research_runs/PAPER1_PLOS_FINAL_20261018/README_zh.md)：结合10月20日说明使用修订Figure 1及保留的Figures 2–7、补充数据 |

HPC下载、提交、实际优化步和checkpoint是不同阶段。学校当前进度应查看操作说明列出的状态路径及实际日志，不能由本页或Slurm的RUNNING状态推断训练完成。

## 冻结科学结果与历史稿件

| 材料 | 如何使用 |
|---|---|
| [eligible-v3扩源结果](../research_runs/ELIGIBLE_V3_RESULTS_20261018/README_zh.md) | 已保存执行结果、预测、源选择与独立审计；论文中的既有扩源结论从这里追溯 |
| [Q15执行证据](../research_runs/Q15-EXECUTION-20261003/README.md) | 保留各作业自己的合同、状态、失败及结果证据；不同job不能互相代替 |
| [Q16生理分析](../research_runs/Q16-P001-BNCI-20261006/PROTOCOL.md) | 冻结描述性分析、参数、结果及独立验证；不作为新HPC算法的训练结果 |
| [Q1–Q16论文版本](../research_runs/PAPER_FINAL_20261006/README.md) | 早期完整论文及对应数字、图表和证据快照 |
| [旧PLOS ONE投稿包](../research_runs/PLOS_ONE_SUBMISSION/README.md) | 历史投稿材料；不是当前HPC运行入口，也不自动成为最新候选稿 |

`research_runs/PAPER*`、`PLOS_ONE*`和日期目录中的稿件是独立版本。应按各自README核对主文、图表、导出和投稿状态，不把不同版本的同名文件混装。GitHub公开与期刊实际收稿、修回或接受不是同一件事。

## 代码与目录分工

| 目录 | 内容 |
|---|---|
| [src/mi_eeg](../src/mi_eeg/) | 原研究的通用数据、模型、评价和复现模块 |
| [configs](../configs/) / [tests](../tests/README.md) | 原研究配置及对应测试；不是新HPC包的全部依赖或运行检查 |
| [experiments](../experiments/) / [results](../results/) / [outputs](../outputs/) | 既有实验入口和按实验身份保存的输出，需结合对应协议解释 |
| [HPC hpcmi](../research_runs/PAPER1_HPC_20261023/hpcmi/) | 学校专用下载、提交、续跑、训练和GitHub同步代码 |
| [HPC config](../research_runs/PAPER1_HPC_20261023/config/) / [HPC tests](../research_runs/PAPER1_HPC_20261023/tests/) | HPC独立配置、版本化输入合同和针对性运行测试 |
| [HPC vendor](../research_runs/PAPER1_HPC_20261023/vendor/) | 固定上游科学实现；运行修复不应直接改写冻结副本 |
| [docs](./) / [paper](../paper/) / [references](../references/) | 研究笔记、早期写作提纲和参考资料；最终稿以对应论文版本目录为准 |

## 数据、断点和身份文件的保留

原始EEG不随Git仓库分发，见[数据政策](../data/README.md)。下载清单、许可、大小及SHA是文件身份记录，不是原始数据本身。凭据不应进入代码、清单或公开日志。

学校项目位于 `/public/home/zhuziyuan/projects/paper1-risk-v1`。整理仓库时不要搬动或重命名其 `raw/`、`raw-nemar-privacy-v1/`、版本化prepared数据、缓存、`outputs/runs/`及其中两代checkpoint、完成记录和逐会话评价。路径与输入身份已经绑定运行配置；隐私版对BNCI/Dreyer的目录链接也需保留。

同样保留项目 `config/paths.json`、`config/data_path.json`、`state/`中的作业登记、源版本历史、下载回执、失败日志和续跑记录。不得删除旧失败以解除锁定、把缺失计数填零，或在新输入版本下冒用旧checkpoint。

仓库中的冻结manifest、选择器、合同、hash、`paper_numbers.json`、科学结果CSV/预测及独立审计应按原路径保留。文档导航可以更新；科研结果或数据身份的变更必须另立版本，不能以文件整理为由覆盖。
