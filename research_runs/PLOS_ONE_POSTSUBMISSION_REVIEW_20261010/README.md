# PLOS ONE 投稿后内部修订候选稿

**Source-only model selection and external evaluation of complete spectral-sharing pipelines in motor-imagery EEG decoding**

作者及通讯作者：Ziyuan Zhu（朱子元）；College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China。

作者报告：该稿件已于 **2026 年 10 月 9 日**提交 PLOS ONE，稿件编号 **PONE-D-26-50597**。已提交题目保留为 “Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding”；上方新题目为候选修订。 本目录是投稿后的作者内部修订候选材料，尚未提交期刊系统，也未替换已提交文件。助手未访问认证投稿页面、发送编辑邮件、撤稿或重复投稿。新版仍需作者审读和批准；此前批准不自动适用于本候选稿。

## 版本与冻结依据

- 候选分支：`paper/plos-one-postsubmission-review-20261010`。
- 本目录：`research_runs/PLOS_ONE_POSTSUBMISSION_REVIEW_20261010/`。
- 已提交版本：[`plos-one-submission-v1.1`](https://github.com/jackzhu119/cross-subject-mi-eeg/tree/plos-one-submission-v1.1/research_runs/PLOS_ONE_SUBMISSION)，保留原目录、标签和文件字节，不覆盖。
- 经核验的科学稿件源：`0c7146895dc46850e4fe7db38bd69d9aea2b41c3`。
- Q15 科学代码：`271af288a2f3863430ab80e3145c2dee9bd5571d`；冻结验证结果：`bc48b257eb44f412ad069f50d0f1a72a33c3c520`。
- Q16 生理参数冻结：`050e01b028aaab8e3d745934b13b2d17e9bb0a7a`。

本轮修订收紧完整管线比较的解释，补充文献和研究问题结构，并将可独立核验的保存预测诊断与原主要分析分开。主要效应、置信区间、p 值、参与者和试次数、训练时长及生理描述均仍来自冻结结果。没有执行新的模型拟合、预测推理或生理实验。专项报告提及的新增源域训练集得分、九折 CSP LOSO 和去均值诊断，需要其相应运行产物才能独立核实，不能仅因报告有该数字就写成已验证结果。

## 候选文件与用途

- `PLOS_ONE_Manuscript.docx`：清洁、可编辑候选主文。
- `PLOS_ONE_Manuscript_Review.pdf`：候选审阅 PDF，供作者核对。
- `SupportingInformation/S1_Appendix.*`：修订补充方法、内部实验编号映射和诊断说明。
- `SupportingInformation/S1_Data.zip`：冻结派生输出；审计新增成员若存在，须在其清单中独立标明来源，不替换原成员。
- `Figures/Fig1.tif` 至 `Fig6.tif`：独立主图；图注与正文统一核对。
- `PLOS_ONE_Submission_Fields.md`：后续经期刊允许时可使用的系统字段草稿。
- `PLOS_ONE_Cover_Letter.md`：修订提交附信草稿；`Editor_Inquiry_Draft.md`：申请提交修订候选稿的邮件草稿，两者均未发送。
- `PLOS_ONE_Submission_Checklist_zh.md`、`Changes_and_Preservation.md`、`Ethics_and_Author_Boundaries.md`：作者核对和证据边界。

本候选的 `Revision_Issue_Matrix.md`、`Revision_Change_Log.md`、`Revision_Integrity_and_Provenance.md`、`Revision_Changes_Diff.html`、`evidence/revision_validation.json` / `.md` 和文件清单应一起审读。旧版验证记录只能证明旧版的相应检查，不能当作本候选稿已经通过验收的证明。完整 ZIP 用于保存和审查，不能代替期刊要求的逐项文件上传；内部清单和技术日志不属于科研补充文件。

## 尚需作者完成

1. 审读本轮新的主文、附录、图表、变更记录和科学证据限度，明确批准候选稿。
2. 核对报告中尚无可追溯运行记录的新 CSP 诊断是否需要取得原始审计产物；未核实内容不得升级为已验证科学结论。
3. 既有公开 ORCID 核查记录显示姓名字段颠倒。作者核对公开 Given name / Family name 应为 Ziyuan / Zhu；不改变 ORCID `0009-0005-1153-4926`，不推断已在期刊账号关联。
4. 如决定申请更换已提交文件，由作者发送编辑询问，并按编辑回复操作。若证实已提交稿存在重要事实错误，应及时据实说明，不等待一般语言修稿。
5. 若获准提交，核对系统生成的合并 PDF、官方 Human Participants Checklist 的 Methods 行号和系统必填声明。文件完成不等于期刊批准更换、接受修订或录用。

## 数据与复现

原始 EEG 不在仓库或本包。官方来源为 [BNCI / BCI Competition IV](https://www.bbci.de/competition/iv/)、[PhysioNet](https://physionet.org/content/eegmmidb/1.0.0/)、[Cho2017](https://gigadb.org/dataset/100295) 和 [Lee2019/OpenBMI](https://gigadb.org/dataset/100542)，各自访问条款继续适用。完整来源、时间证据与许可说明见 `PLOS_ONE_Data_Availability.md`、`LICENSING.md` 及 `evidence/research_access_dates.json`。

科学重跑步骤保留在[不可变科学复现指南](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/0c7146895dc46850e4fe7db38bd69d9aea2b41c3/research_runs/PAPER_FINAL_20261006/reproducibility_readme.md)。本轮未执行该指南中的模型或原始 EEG 重跑命令。保存输出核对、文档导出和原实验复现的范围不同，见 `REPRODUCIBILITY.md`。本次不创建正式 v1.2 Release，也不声称已有新 DOI。

## Archive verification

The full ZIP includes content_validation.json and all manuscript, data, figure and audit material. The final full-ZIP readback receipt revision_validation.json/md and GitHub publication receipt are adjacent files on this branch, intentionally outside the ZIP and SHA256SUMS to avoid recursive checksum binding. Check the ZIP .sha256 sidecar before extracting. No v1.2 journal replacement or formal release is authorized by this archive.
