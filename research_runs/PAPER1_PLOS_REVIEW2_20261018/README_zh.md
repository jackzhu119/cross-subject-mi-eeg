# 论文1：PLOS ONE 更新稿（2026-10-18）

**Source-cohort expansion improves weaker-class coverage in cross-subject motor-imagery EEG decoding**

本目录是基于最新已完成扩源实验的独立论文更新包。原稿作者报告已于 **2026-10-09** 提交 PLOS ONE，稿号 **PONE-D-26-50597**；当前文件是等待编辑许可纳入的更新候选材料，不是第二份并行投稿。稿件分支：`paper/p1-plos-review2-20261018`。冻结结果提交：`040956085499ed788948de0d5a09cddd9eabca56`；执行代码内容对应 `0539379578818b3d71f995192e5e8a81cf4d5aef`。历史 main、Q1–Q16、原投稿及结果不由本目录覆盖。

## 先读和上传哪些文件

| 内容 | 文件 |
|---|---|
| 英文主文源 | `manuscript_en.md` |
| 主文投稿文件 | `main_manuscript.docx` |
| 阅读校对版 | `review_manuscript.pdf` |
| 补充材料源与导出 | `supplementary_en.md`、`S1_Appendix.docx`、`S1_Appendix.pdf` |
| 精简表/图源数据 | `S1_Data.zip` |
| 完整保存预测 | `S2_Neural_Predictions.csv.gz`、`S3_CSP_Predictions.csv.gz` |
| 主图 | `figures/Fig*.tif`，其矢量/预览源随包保存 |
| 投稿信 | `submission/Cover_Letter.md`、`.docx`、`.pdf` |
| 门户字段与作者待办 | `submission/Submission_Fields.md`、`submission/Submission_Checklist_zh.md` |
| 作者伦理说明 | `submission/Ethics_Author_Statement.md`，及其 DOCX/PDF 导出；这是作者说明，不是学校签发文件 |
| 数据许可与归属 | `submission/Licensing_and_Provider_Terms.md`，含本次核验的 Yang v5 / Dreyer 原存档 CC BY 4.0 元数据来源 |
| 可复现说明与发布边界 | `REPRODUCIBILITY.md`、`RELEASE_CHECKLIST.md` |

已完成实验包含 108 条神经轨迹及 9 次传统基线拟合。固定 BROAD/tail-minimum-recall 比较中，S60 对 S9 的较弱类召回率提高 21.1667 个百分点，平衡准确率提高 5.8529 个百分点。全部预设比较、未显著结果、传统基线和参与者差异均保留，避免把队列扩展证据改写成尚未建立的普适算法优势。

独立外评审计的 1,179 项检查全部通过；独立源选择和完整性证据另行保存。检查范围及归档位置在可复现说明中明确。原始 EEG 不在仓库；BNCI、Yang、Dreyer 的来源与版本链接见 `submission/Data_Availability.md`。本更新只使用现有冻结输出进行写作、绘图和出版导出，不执行模型训练或新预测。

作者姓名按本人确认统一为 **Ziyuan Zhu**（Given: Ziyuan；Family: Zhu），正确 ORCID 为 **0009-0005-1153-4926**。主文和 DOCX 元数据按此更新；未修改外部 ORCID 账户。论文1的免审依据按本人最新确认更新：**2026-10-17 重庆医科大学科研处，2023 年办法第三十二条第（一）项，覆盖 BNCI、Yang、Dreyer**。不混用论文2日期，不编造编号或学校证明。

请作者完成当前新版本及门户 PDF 的最终审读，并按编辑实际许可更新原稿。当前包不冒充期刊正式修回邀请、不自动提交、不声称已取得 DOI 或完成尚未落实的 R2 全量回读。

## 本次加强的贡献与新增展示

1. 主比较：固定完整轨迹预算下，较弱类召回改善21.17 pp、平衡准确率改善5.85 pp；全部85人变化中72人改善。
2. 相同选中时长的对照：20轮/2,560次更新时，S60−S9弱类召回改善17.07 pp（宽频）和24.87 pp（共享双频）。全部24项种子、扩源、流程和端点差值均为正；这是同一外部队列的描述性一致性，并非独立重复研究。
3. 四项明确事后推断：S29−S9宽频弱类召回改善21.72 pp，CSP的S60−S9改善13.82 pp，两组均同时报告平衡准确率，使用独立Holm四检验族，不改原预设检验。
4. 类别覆盖分解：平均左右召回差距从62.0098降至31.3824 pp。这是已有端点的代数分解，没有新增假设检验。
5. 七图、五张主文表及完整68项扩源描述清单，使主比较、个体变化、所有48个选轮、补充推断和固定时长对照均可逐项核对。重复防御性文字已收紧，必要范围集中在方法与讨论末段。

完整文件及 SHA256 见 `MANIFEST.sha256`；投稿整理包为 `Paper1_PLOS_ONE_Review2_20261018.zip`，它是供作者保存和拆分上传的目录包，不应作为单个主文文件上传。正式上传：主文 DOCX、7 个 TIFF、S1 Appendix、S1/S2/S3 Data、投稿信及门户要求的作者表单。

固定时长对照见Table5/Fig7：20轮同2560更新时，宽频/共享双频的S60−S9弱类召回改善17.0686/24.8725 pp，全部24项种子变化为正。完整68项清单保留所有方向。GitHub写入受当前权限限制，远端未更新；本地DOCX/整理包及Git bundle可用。
