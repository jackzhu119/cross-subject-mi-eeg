# PLOS ONE 投稿材料

Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding

作者：Ziyuan Zhu；College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China。

**当前目标期刊为 PLOS ONE，材料已按该刊准备；尚未正式提交。** 本人已提供 ORCID、批准当前稿件并确认贡献、原创输出许可和自付出版费；仍须更正 ORCID 姓名字段、在系统关联 iD、审读系统合并 PDF 并完成最终声明。文件制作、公开备份和技术校验不等于期刊审核通过或录用。

当前论文分支：`paper/plos-one-author-finalization-20261009`；对应发布标签：`plos-one-submission-v1.1`。科学内容沿用已核验稿件源 snapshot `0c7146895dc46850e4fe7db38bd69d9aea2b41c3`，Q1–Q16 冻结结果未改。历史版本以 Git 提交及既有标签保存；当前投稿材料以本目录为准。

## 下载及上传

- [完整材料包](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.1/research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Submission_Package.zip)
- [可编辑主文](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.1/research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Manuscript.docx)
- [审阅 PDF](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.1/research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Manuscript_Review.pdf)
- [投稿信](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.1/research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Cover_Letter.docx)
- [补充材料](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.1/research_runs/PLOS_ONE_SUBMISSION/SupportingInformation/S1_Appendix.pdf)
- [冻结派生数据](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.1/research_runs/PLOS_ONE_SUBMISSION/SupportingInformation/S1_Data.zip)

完整包包含主文、审阅 PDF、投稿信、六张 TIFF、补充文件、系统填写文本、费用指南、清单、验证记录及 SHA-256；`AuthorForms/` 附 PLOS 官方 Human Participants Checklist 原版空白表和依据作者事实、审计日期及当前 Methods 行号完成的表格；该表是独立行政附件，不能当作科研补充文件上传。投稿时分别上传 DOCX、投稿信、`Figures/Fig1.tif` 至 `Fig6.tif`、S1 Appendix 和 S1 Data。审阅 PDF 供本人核查，正式系统生成的合并 PDF 还须检查。不要用完整 ZIP 替代主文，也不要把内部清单作为科研补充文件上传。

## 投稿前需要本人完成

先阅读 `PLOS_ONE_Submission_Checklist_zh.md`。已确认 ORCID 0009-0005-1153-4926、当前版本批准、独立作者贡献、无资助和利益冲突、自付出版费、不申请减免、无回避审稿人及原创输出许可。公开 ORCID 的 Given name / Family name 当前颠倒，本人须改为 Ziyuan / Zhu 并在投稿系统关联 iD。核对系统生成的 PDF、提交当日独占投稿状态和必填声明；无正式伦理文件，若期刊询问适用依据则如实说明，不声称学校批准或正式豁免。

## 冻结结果与复现

Q15 验证结果 commit：`bc48b257eb44f412ad069f50d0f1a72a33c3c520`；Q16 参数冻结：`050e01b028aaab8e3d745934b13b2d17e9bb0a7a`。原始 EEG 不在本包，官方数据来源和冻结输入路径见 `PLOS_ONE_Data_Availability.md`。科学重跑说明见[不可变源复现指南](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/0c7146895dc46850e4fe7db38bd69d9aea2b41c3/research_runs/PAPER_FINAL_20261006/reproducibility_readme.md)；本次只做编辑、导出和保存结果核对，没有执行这些科学重跑命令。

编辑导出脚本 `build_plos_package.py` 只读冻结文本、输出和矢量图；生成 DOCX 后使用 LibreOffice 导出 PDF，由 `validate_plos_package.py` 检查结果保护、文字、引用、表格、图形及文件。完整包附 `FILE_INVENTORY.json`、`MANIFEST.sha256` 和包的 SHA-256 侧文件。字体使用本机 Arial，字体文件不随包分发；未创建 Zenodo DOI。
