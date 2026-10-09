# PLOS ONE 投稿材料

Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding

作者：Ziyuan Zhu；College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China。

**当前目标期刊为 PLOS ONE，材料已按该刊准备；尚未正式提交。** 投稿前本人仍须完成下方清单中的 ORCID、当前文件审读、真实声明与费用安排。文件制作、公开备份和技术校验不等于期刊审核通过或录用。

当前论文分支：`paper/plos-one-submission-20261009`；对应发布标签：`plos-one-submission-v1.0`。科学内容沿用已核验稿件源 snapshot `0c7146895dc46850e4fe7db38bd69d9aea2b41c3`，Q1–Q16 冻结结果未改。历史版本以 Git 提交及既有标签保存；当前投稿材料以本目录为准。

## 下载及上传

- [完整材料包](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.0/research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Submission_Package.zip)
- [可编辑主文](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.0/research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Manuscript.docx)
- [审阅 PDF](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.0/research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Manuscript_Review.pdf)
- [投稿信](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.0/research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Cover_Letter.docx)
- [补充材料](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.0/research_runs/PLOS_ONE_SUBMISSION/SupportingInformation/S1_Appendix.pdf)
- [冻结派生数据](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/plos-one-submission-v1.0/research_runs/PLOS_ONE_SUBMISSION/SupportingInformation/S1_Data.zip)

完整包包含主文、审阅 PDF、投稿信、六张 TIFF、补充文件、系统填写文本、费用指南、清单、验证记录及 SHA-256；`AuthorForms/` 另附 PLOS 官方 Human Participants Checklist 空白表及真实填写说明，须本人完成，不能当作科研补充文件上传。投稿时分别上传 DOCX、投稿信、`Figures/Fig1.tif` 至 `Fig6.tif`、S1 Appendix 和 S1 Data。审阅 PDF 供本人核查，正式系统生成的合并 PDF 还须检查。不要用完整 ZIP 替代主文，也不要把内部清单作为科研补充文件上传。

## 投稿前需要本人完成

先阅读 `PLOS_ONE_Submission_Checklist_zh.md`。通讯作者 ORCID 尚未提供；新的 PLOS 排版稿仍须本人审读批准。贡献角色、当前独占投稿状态、学校二次分析伦理要求、数据/代码许可和 APC 支付或申请减免的答案须真实确认。已确认的无资助、无利益冲突、作者姓名/单位/邮箱保持不变。

## 冻结结果与复现

Q15 验证结果 commit：`bc48b257eb44f412ad069f50d0f1a72a33c3c520`；Q16 参数冻结：`050e01b028aaab8e3d745934b13b2d17e9bb0a7a`。原始 EEG 不在本包，官方数据来源和冻结输入路径见 `PLOS_ONE_Data_Availability.md`。科学重跑说明见[不可变源复现指南](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/0c7146895dc46850e4fe7db38bd69d9aea2b41c3/research_runs/PAPER_FINAL_20261006/reproducibility_readme.md)；本次只做编辑、导出和保存结果核对，没有执行这些科学重跑命令。

编辑导出脚本 `build_plos_package.py` 只读冻结文本、输出和矢量图；生成 DOCX 后使用 LibreOffice 导出 PDF，由 `validate_plos_package.py` 检查结果保护、文字、引用、表格、图形及文件。完整包附 `FILE_INVENTORY.json`、`MANIFEST.sha256` 和包的 SHA-256 侧文件。字体使用本机 Arial，字体文件不随包分发；未创建 Zenodo DOI。
