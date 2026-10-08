# PLOS ONE备用投稿包

Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding

作者：Ziyuan Zhu；College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China。

**JNE 已提交、仍在审稿（作者确认）；PLOS ONE 正式投稿被阻断。** 这里只制作备用包，不代表撤稿、PLOS 投稿、减免、录用或付款。

科学内容取自最新核验分支 `paper/zero-calibration-q16-20261006`，源 commit `0c7146895dc46850e4fe7db38bd69d9aea2b41c3`；源稿件 artifact tag `paper-v1.0.2`（`b23480d996dd6c78e386686e1110e272decf166f`）。新分支 `paper/plos-one-submission-20261008`。源 JNE 文件及 Q1–Q16 结果保持不变。

## 下载

- [完整包](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-preparation-v0.1/research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Preparation_Package.zip)
- [可编辑主文](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-preparation-v0.1/research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Manuscript.docx)
- [审阅 PDF](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-preparation-v0.1/research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Manuscript_Review.pdf)
- [补充材料](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-preparation-v0.1/research_runs/PLOS_ONE_SUBMISSION/SupportingInformation/S1_Appendix.pdf)
- [冻结派生数据](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-preparation-v0.1/research_runs/PLOS_ONE_SUBMISSION/SupportingInformation/S1_Data.zip)

完整包包含主文、审阅 PDF、备用投稿信、六张 TIFF、补充文件、系统填写文本、费用指南、清单、验证及 SHA-256。`Figures` 应逐图上传；内置清单不是科研补充材料，不能用完整 ZIP 替代主文。

## 阅读与下一步

先看 `PLOS_ONE_Submission_Checklist_zh.md`，尤其 JNE 状态、ORCID、学校伦理政策、真实 CRediT、数据/代码许可及 APC 资金。新 PLOS 排版稿仍须本人审读批准。

Q15 验证结果 commit `bc48b257eb44f412ad069f50d0f1a72a33c3c520`；Q16 参数冻结 `050e01b028aaab8e3d745934b13b2d17e9bb0a7a`。原始 EEG 不在本包，官方来源及冻结输入路径见 `PLOS_ONE_Data_Availability.md`。所有原始科学重跑说明沿用 [不可变源复现指南](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/0c7146895dc46850e4fe7db38bd69d9aea2b41c3/research_runs/PAPER_FINAL_20261006/reproducibility_readme.md)；本次没有执行这些科学重跑命令。

编辑导出脚本 `build_plos_package.py` 只读冻结文本/输出和矢量图；生成 DOCX 后使用 LibreOffice 导出 PDF，运行 `validate_plos_package.py` 做出版检查。重复生成会更新编辑文件，不能用来改冻结结果。字体使用本机 Arial；字体文件不随包分发。尚未创建 Zenodo DOI。
