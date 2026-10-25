# 论文1：研究、稿件与运行目录索引

本页只整理入口，原目录、冻结结果、旧稿和失败记录均保留原位。**eligible-v3结果、当前论文候选和学校HPC新算法实验分别编目**：论文引用已完成研究；后续新实验的完成状态单独判断。

## 当前学校 HPC 实验

| 入口 | 内容 |
|---|---|
| [运行包说明](PAPER1_HPC_20261023/README_zh.md) | 新算法实验范围、数据与输出；不代表已有新训练结论 |
| [单作业启动与续跑](PAPER1_HPC_20261023/SINGLE_JOB.md) | `hpc_gpu`；一个作业、一个节点、2 GPU、总 24 CPU、总 128G |
| [数据下载入口](PAPER1_HPC_20261023/DOWNLOAD_ENTRIES.md) | 下载来源与逐对象清单；实际下载状态以现场校验记录为准 |
| [研究协议](PAPER1_HPC_20261023/PROJECT_PROTOCOL.md) / [分析计划](PAPER1_HPC_20261023/ANALYSIS_PLAN.md) | 新实验的方法、比较与统计定义 |

运行入口和文件身份以该目录最新说明及实际执行记录为准；历史 RunPod 命令不用于学校任务。

## 当前论文候选与投稿配套

当前主文是 **2026-10-20 的有限文字修订稿**：*Source-cohort expansion improves weaker-class coverage in cross-subject motor-imagery EEG decoding*。该目录记录关联稿号 PONE-D-26-52176；仓库文件不证明投稿系统中已上传或采用同一版本。

| 用途 | 入口 |
|---|---|
| 当前主文 | [DOCX](PAPER1_REVIEW_20261020/main_manuscript.docx) · [PDF](PAPER1_REVIEW_20261020/main_manuscript.pdf) · [Markdown 源](PAPER1_REVIEW_20261020/manuscript_en.md) |
| 当前候选说明与修改依据 | [README](PAPER1_REVIEW_20261020/README.md) · [意见甄别表](PAPER1_REVIEW_20261020/EDITORIAL_TRIAGE_zh.md) · [导出验证](PAPER1_REVIEW_20261020/RELEASE_VALIDATION.json) |
| 当前 S1 Appendix 与投稿信 | [补充材料 DOCX](PAPER1_REVIEW_20261020/S1_Appendix.docx) · [投稿信 DOCX](PAPER1_REVIEW_20261020/Cover_Letter.docx) |
| 当前 Figure 1 | [修订图目录](PAPER1_REVIEW_20261020/figures/)；仅 panel F 文案更新 |
| 其余图、支持数据与作者材料 | [2026-10-18 配套包](PAPER1_PLOS_FINAL_20261018/README_zh.md) · [Figures 2–7 所在目录](PAPER1_PLOS_FINAL_20261018/figures/) · [S1 Data](PAPER1_PLOS_FINAL_20261018/S1_Data.zip) · [S2 神经预测](PAPER1_PLOS_FINAL_20261018/S2_Neural_Predictions.csv.gz) · [S3 CSP 预测](PAPER1_PLOS_FINAL_20261018/S3_CSP_Predictions.csv.gz) · [S4 Data](PAPER1_PLOS_FINAL_20261018/S4_Data.zip) · [submission](PAPER1_PLOS_FINAL_20261018/submission/) |

使用 10 月 20 日主文与 Figure 1 时，保留其 README 指定的配套关系。[10 月 18 日 Review2](PAPER1_PLOS_REVIEW2_20261018/README_zh.md) 是更早的候选稿，不是另一套新增科学结果。

## 已完成的 eligible-v3 结果、资格定义与冻结证据

| 入口 | 内容 |
|---|---|
| [结果总览](ELIGIBLE_V3_RESULTS_20261018/README_zh.md) | 108 条神经训练轨迹、9 次传统模型拟合及已保存预测的证据范围 |
| [中文结果](ELIGIBLE_V3_RESULTS_20261018/RESULTS_REVIEW_zh.md) / [英文 Methods–Results](ELIGIBLE_V3_RESULTS_20261018/METHODS_RESULTS_REVISION_en.md) | 对应已完成研究；不是 HPC 新方法结果 |
| [源选择冻结](ELIGIBLE_V3_RESULTS_20261018/indexed/results/selection_freeze.json) / [执行来源](ELIGIBLE_V3_RESULTS_20261018/indexed/provenance/) | 原执行配置、代码身份、源选择与拟合记录 |
| [独立复核目录](ELIGIBLE_V3_RESULTS_20261018/audits/) / [原始导出证据](ELIGIBLE_V3_RESULTS_20261018/evidence/) | 保存预测、源选择和归档完整性的核对记录 |
| [标签资格修订](YANG_LABEL_ELIGIBILITY_20261018/README_zh.md) / [时钟登记恢复](YANG_CLOCK_RECOVERY_20261018/README_zh.md) / [事件标记审计](YANG_MARKER_AUDIT_20261018/README_zh.md) | eligible-v3 使用的原输入资格、时钟与事件依据 |
| [原扩源实验代码](SOURCE_EXPANSION_20261017/README_zh.md) | 该轮实验的代码与配置历史 |

结果冻结提交为 `040956085499ed788948de0d5a09cddd9eabca56`，实际执行代码内容对应 `0539379578818b3d71f995192e5e8a81cf4d5aef`。新下载路线或新输入版本的准备完成，不等于旧研究被重新训练或验证。

## 早期研究与 Q1–Q16 历史

| 入口 | 内容 |
|---|---|
| [早期研究记录](../docs/research_progress.md) | 早期审计、P 系列与 Q4 记录；文中的阶段状态按其日期理解 |
| [完成实验清单](PAPER_FINAL_20261006/tables/completed_experiment_inventory.csv) / [内部实验清单](PAPER_FINAL_20261006/tables/completed_internal_inventory.csv) / [早期质量检查清单](PAPER_FINAL_20261006/tables/early_binary_qc_inventory.csv) | 区分实验、复用、质量检查与失败分支，不能把行数当独立实验数 |
| [Q1–Q16 论文证据材料](PAPER_FINAL_20261006/README.md) / [冻结论文数值](PAPER_FINAL_20261006/paper_numbers.json) | 历史论文数值、图表和审计输入；不是当前扩源主文 |
| [Q15 数值审计](PAPER_FINAL_20261006/evidence/q15_numbers.json) / [Q15 执行历史](Q15-EXECUTION-20261003/README.md) | 已归档外评与执行证据；不同作业身份保留 |
| [Q16 冻结协议](Q16-P001-BNCI-20261006/PROTOCOL.md) / [Q16 独立验证](Q16-P001-BNCI-20261006/independent_validation.md) | 已完成的 BNCI 描述性生理分析 |
| [历史 results](../results/) | 按原实验编号保存的输出、冻结与验证记录 |

[`paper/outline.md`](../paper/outline.md)、[`docs/manuscript_sample.md`](../docs/manuscript_sample.md) 和 [`docs/expanded_manuscript_sample.md`](../docs/expanded_manuscript_sample.md) 是早期提纲或样例，不是当前投稿主文。

## 旧投稿与旧 RunPod 恢复历史

- [早期 PLOS ONE 投稿包](PLOS_ONE_SUBMISSION/README.md)、[投稿后复核](PLOS_ONE_POSTSUBMISSION_REVIEW_20261010/README.md)、[10 月 18 日 Review2](PAPER1_PLOS_REVIEW2_20261018/README_zh.md)：按原版本保留，不当作当前门户状态。
- [旧 RunPod 执行包](REDESIGN_CLOUD_20261013/README.md)、[10 月 14 日恢复交接](REDESIGN_HANDOFF_20261014/HANDOFF.md)、[10 月 15 日恢复交接](REDESIGN_HANDOFF_20261015/README.md)：保留原失败、恢复与授权上下文，不作为学校 HPC 的启动命令。

这些目录含固定提交引用、相对路径、文件清单与哈希绑定；本次通过索引整理，**不移动或重命名原文件**。原始 EEG、凭据和大型训练权重不因本索引进入仓库。
