# 论文1：IJBET 投稿材料与既有结果整理（2026-10-29）

目标期刊：**International Journal of Biomedical Engineering and Technology**，Inderscience。

当前交付为 **v2**：按作者校正AI披露，Codex辅助代码修改、GitHub推送和文件汇总整理，ChatGPT辅助语法修正和期刊格式查询。科研正文、表格与图件未改，旧版交付保留。修订与文件身份见 `evidence/AI_DISCLOSURE_REVISION_v2.json` 和 `RELEASE.json`。

本次完成英文稿件重写、期刊格式转换、参考文献核查和两幅原创结果图。使用英文版 `anti-defensive-writing` 技能，将研究问题、实际贡献和主要阳性结果放在摘要与引言前部。正文保留决定结论的完整比较；没有新增训练、推理、统计检验或实验。

## 本稿使用哪些数据版本

| 版本 | 已完成内容 | 本稿用途 |
|---|---|---|
| eligible-v3，2026-10-18 | 108条神经网络训练轨迹、9个CSP–LDA模型 | Study 1：源队列配置、同训练时长对照、参与者覆盖 |
| 学校HPC source-risk-v1，2026-10-27 | 90条神经网络训练轨迹；原预测已独立复核 | Study 2：5种目标函数的匹配比较 |
| composition-v2，630项计划 | 最近读取的进度快照仍未完成 | 未写入本稿结果，未更改或停止现场任务 |

两项完成研究使用相同85名外部参与者，但数据重建身份、实现、批量和选轮方案有区别。稿件分别报告，不合并效应、不写成独立外部复现。历史19通道稿件与旧投稿继续保留。

主证据为既存的 **W +21.17个百分点、BA +5.85个百分点、66/85人双指标改善**。等时长控制与传统方法支持源配置结果；TC相对GroupDRO的优势按具体比较报告。来源、精确数值及完整比较见 `evidence/` 和 `figure_data/`。

## 文件组织

- `figures/`：两幅图的彩色及IJBET黑白版，PNG/PDF/SVG。
- `figure_data/`：85名参与者变化、12个目标函数对比、三份原分析JSON和来源哈希。
- `supporting_data/`：复制既有完整统计表、固定20轮对照、全选择规则清单；未重新估计统计量。
- `evidence/`：版本核查、官方格式要求、参考文献元数据、数值和版式核查。
- `LITERATURE_STRUCTURE_NOTES_zh.md`：两篇指定论文的实际阅读范围及通用论证结构，不移用其结果。

完整可下载交付另包含匿名主稿PDF/DOCX、作者信息DOCX、投稿信DOCX、可编辑源和投稿操作说明。匿名稿与具名编辑材料分别保存，不把专家候选个人关系核查资料混入公开仓库。

## 投稿格式

当前匿名稿15页，摘要132词、关键词12项，4表2图，Harvard作者–年份引用，UK English，图置文末。Word正文使用12pt Times New Roman；PDF渲染采用兼容的Liberation Serif字体。匿名稿正文及文件属性已检查，不含作者、邮箱、学校或识别性仓库链接。

官方依据（核查于2026-10-29）：

- [IJBET主页](https://www.inderscience.com/jhome.php?jcode=ijbet)
- [作者指南](https://www.inderscience.com/authorguidelines/)
- [准备稿件](https://www.inderscience.com/mobile/inauthors/index.php?pid=71)
- [提交清单](https://www.inderscience.com/mobile/inauthors/index.php?pid=72)
- [在线投稿系统](https://www.indersciencesubmissions.com/)

官方预印本条款将认可的仓储定义为非营利、开放获取、CC-BY的机构或学科仓储，未明确列出GitHub。为避免新增不明确的公开稿件状态，本次新完整投稿文件在下载包中交付；公开目录只保存既有结果的图表、来源和核查说明。先前公开材料在给编辑的文件中披露，原历史不删除、不改写。本次未代为投稿或联系编辑、专家。

## 图表重建

在已具备NumPy和Matplotlib的独立文档环境中，可执行：

```bash
python build_figures_ijbet.py
```

脚本只读取这里的冻结CSV并输出图像，不读取原始EEG或模型。输出PDF/SVG可能带新时间信息；数值来源哈希、点数和区间保持不变。现场训练环境无需安装或执行本目录内容。
