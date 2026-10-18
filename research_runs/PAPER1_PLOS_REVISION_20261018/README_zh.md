# 论文1：PLOS ONE 更新稿（2026-10-18）

**Source-cohort expansion and weaker-class coverage in cross-subject motor-imagery EEG decoding**

本目录是基于最新已完成扩源实验的独立论文更新包。稿件分支：`paper/p1-plos-evidence-update-20261018`。冻结结果提交：`040956085499ed788948de0d5a09cddd9eabca56`；执行代码内容对应 `0539379578818b3d71f995192e5e8a81cf4d5aef`。历史 main、Q1–Q16、原投稿及结果不由本目录覆盖。

## 先读和上传哪些文件

| 内容 | 文件 |
|---|---|
| 英文主文源 | `manuscript_en.md` |
| 主文投稿文件 | `main_manuscript.docx` |
| 阅读校对版 | `review_manuscript.pdf` |
| 补充材料源与导出 | `supplementary_en.md`、`S1_Appendix.docx`、`S1_Appendix.pdf` |
| 精简表/图源数据 | `S1_Data.zip` |
| 主图 | `figures/Fig*.tif`，其矢量/预览源随包保存 |
| 投稿信 | `submission/Cover_Letter.md`、`.docx`、`.pdf` |
| 门户字段与作者待办 | `submission/Submission_Fields.md`、`submission/Submission_Checklist_zh.md` |
| 可复现说明与发布边界 | `REPRODUCIBILITY.md`、`RELEASE_CHECKLIST.md` |

已完成实验包含 108 条神经轨迹及 9 次传统基线拟合。固定 BROAD/tail-minimum-recall 比较中，S60 对 S9 的较弱类召回率提高 21.1667 个百分点，平衡准确率提高 5.8529 个百分点。全部预设比较、未显著结果、传统基线和参与者差异均保留，避免把队列扩展证据改写成尚未建立的普适算法优势。

独立外评审计的 1,179 项检查全部通过；独立源选择和完整性证据另行保存。检查范围及归档位置在可复现说明中明确。原始 EEG 不在仓库；BNCI、Yang、Dreyer 的来源与版本链接见 `submission/Data_Availability.md`。本更新只使用现有冻结输出进行写作、绘图和出版导出，不执行模型训练或新预测。

请作者完成当前新版本及门户 PDF 的最终审读，并确认真实投稿状态。当前包不冒充期刊正式修回邀请、不自动提交、不声称已取得 DOI 或完成尚未落实的 R2 全量回读。

## 本次加强的贡献与新增展示

1. 以固定完整轨迹更新预算的源队列扩展为主线，将 21.17 pp 的较弱类召回改善与 5.85 pp 的平衡准确率改善并列报告。
2. 全部 85 人配对变化图保留 72 改善、10 下降、3 不变；读者可核对平均效应与个体分布。
3. 增加明确标注的描述性代数分解：平均左右召回差距从 62.0098 降至 31.3824 pp。没有新增显著性检验。
4. 新增完整四项比较森林图、三种管线的端点图及全部 48 项选轮矩阵，展示固定预算与实际选中时长的区别。
5. 重写引言、讨论和结论，减少重复防御性句式；以可核验贡献替代夸大，不隐藏影响判断的结果。

完整文件及 SHA256 见 `MANIFEST.sha256`；投稿整理包为 `Paper1_PLOS_ONE_20261018.zip`，它是供作者保存和拆分上传的目录包，不应作为单个主文文件上传。正式上传：主文 DOCX、5 个 TIFF、S1 Appendix、S1 Data、投稿信及门户要求的作者表单。
