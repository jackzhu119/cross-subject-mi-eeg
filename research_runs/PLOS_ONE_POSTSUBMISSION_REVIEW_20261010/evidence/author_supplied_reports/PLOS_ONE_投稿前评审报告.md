# 投稿前评审报告

**论文**：Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding
**作者**：Ziyuan Zhu（朱子元），重庆医科大学 人工智能学院
**目标期刊**：PLOS ONE
**评审日期**：2026-10-10
**评审范围**：主文稿（42 页双倍行距投稿稿、8 张表、6 张图、28 篇参考文献）、S1 Appendix（29 页，Tables S1–S4、Figures S1–S3、详细方法 S1–S10）、S1 Data（68 个文件：预测、表格、协议、验证证据）、投稿信、摘要、标题/关键词、投稿字段、数值验证报告、图表质量报告。

---

## 一、总体判断

**未发现足以直接拒稿（CRITICAL）的硬伤**：论文逻辑链完整，主张与证据基本对得上，且几乎所有主张都做了恰当的限定；图表符合 PLOS 技术规范；我抽查的 15 个以上关键数字与冻结权威文件 `paper_numbers.json` **逐一吻合**。

但存在 **7 项一审会被点（MAJOR）的问题**和若干打磨项，因此**现在还不能直接投**。其中两项实质问题（M1、M2）建议用**只做推理、不拟合目标数据**的补充分析解决，这与你的零校准契约不冲突。

**最该先修的三件事**：
1. 诊断外部 CSP 比较器为何在两个外部队列上几乎只预测一个类别（M1）——若无法排除实现错误，该问题升级为 CRITICAL。
2. 补一次**固定相同时长**的外部 broad/shared 推理对比，或修改标题措辞（M2），否则你唯一的显著性结果（Cho −1.513pp）无法归因于"频谱共享"。
3. 补齐文献定位（M5）：有 6 篇与你主题高度重合的已发表工作未被引用。

**投稿建议**：不属于推倒重来的大改，核心工作扎实；建议预留约 3–5 天完成两项推理级补充分析 + 文献/摘要/引言修订，**修改后可投**。

---

## 二、第一层：整体逻辑

论文叙事为"模型选择审计 → 冻结外部评估 → 描述性生理分析"三条线，脉络清楚，Fig 1 的信息边界图与正文一致。逻辑层面有两处需要补强：

### M3（MAJOR）引言缺少明确的贡献清单

引言以第 21 行 "Here, we audit source-only model selection as part of cross-subject decoder evaluation [11]." 收束，但没有逐条列出贡献；唯一点明贡献的句子埋在 Related Work 第 31 行："Our contribution is an audit of source-only model selection, participant heterogeneity and complete frozen-pipeline transfer, with adverse and null results retained in a traceable evidence record."

审稿人需要在引言末尾直接看到贡献清单。**修法**：在第 21 行后增加 4 条要点，例如：
1. 审计证据：source-only 时长选择可能导致极短训练与单类预测崩溃，按折秩聚合（mean-rank）会改变所选日程；
2. 冻结的多队列外部评估：shared mu/beta 无一致优势，含一个经多重比较校正后的显著不利结果（Cho2017）；
3. 描述性 BNCI 生理特征及其与 LOSO BA 的关联，明确不主张解码器机制；
4. 字节级可审计的复现包（预测、协议、校验和）。

### 贯穿锚点基本到位但可强化

S3 这个例子在引言（第 17 行 "A decoder that predicts predominantly one class can have balanced accuracy near chance…"）、方法（第 125 行 S3 四格诊断）、结果（Fig 2C）三处反复出现，是合格的贯穿锚点。建议在 Fig 2C 图题或正文中明确点出"该单例不构成人群层面结论"（你已在第 125、295 行说明，保留即可）。

---

## 三、第二层：主张与证据

### M1（MAJOR，可能升级 CRITICAL）外部 CSP 比较器在两个队列上崩溃，尚未排除实现问题

Table 7 显示 CSP4+LDA 在外部队列上的逐类召回：
- Cho2017：左手 **94.10%**、右手 **9.88%**；
- Lee2019：左手 **85.98%**、右手 **19.56%**。

即 CSP 在**两个相互独立的外部队列上同向地几乎只预测一个类别**，而内部二分类 CSP 工作正常（P2 cross-subject 62.76%，Table S3）。正文第 397 行仅作描述："The CSP comparator was near binary chance on both cohorts and strongly favoured left-hand labels."

审稿人一定会问：**这是真实的跨协议迁移失败，还是 Q15 CSP 适配器（CAR → Helmert → 未正则 CSP → StandardScaler）的实现错误？** 若是后者，会连带动摇整个 Q15 评估的可信度。你已有的 raw-to-prediction 重放验证只能证明代码能复现自己，不能证明 CSP 设计正确。

支持"真实崩溃而非标签反转"的证据是：神经模型在外部队列上达到 60–66% BA（若标签整体反转，BA 应落在约 35–40%），说明神经管线的标签映射正确，问题更可能是未正则 CSP 在跨协议协方差漂移下的脆弱性。但这需要你主动证明。

**修法**（新增一小段诊断，纯推理/统计，不拟合目标）：
1. 报告 CSP 在源内验证折上的 BA（应约 60%+），证明源端正常；
2. 报告两个外部队列上 CSP 的预测类别比例与逐人混淆，定位崩溃发生在"源内正常→外部单类"的哪一环；
3. 对 Helmert 坐标下的协方差尺度/StandardScaler 做一次对照检查（例如对比 source-clean 与外部的协方差迹量级）；
4. 在讨论中明确这是 CSP 管线的跨协议脆弱性，而非解码器普遍结论。
**若上述检查无法排除实现错误，此项按 CRITICAL 处理，不应投稿。**

### M2（MAJOR）唯一的显著结果被训练时长混杂，标题却读作因果断言

外部 broad/shared 的训练时长并不相同：Q14 为 18/17  epoch，Q15 为 **14/19** epoch（第 187、199 行）。论文对此高度自觉，多处写明：
- 第 43 行："Each contrast therefore evaluates complete selected pipelines rather than the isolated effect of sharing."
- 第 199 行："…cannot isolate parameter sharing or band decomposition alone."
- 第 441 行："They do not identify the causal contribution of parameter sharing alone."

但标题是 "**…limits of fixed spectral-sharing pipelines…**"，摘要与结果的头条是 Cho 上 shared 显著更差（−1.513pp，Holm p<0.001）。在 14 vs 19 epoch 的设计下，这个显著差异**可能全部来自训练时长**，标题和头条会被读作关于"共享"的因果断言。

**修法（二选一，推荐前者）**：
1. **补一次固定相同时长的外部对比**：用 Q15 已有的适配器与冻结模型族，对 broad 与 shared 各以固定相同 epoch（如 20）在 Cho/Lee 上只做推理，再算配对差异。这是纯目标推理、不做任何目标拟合，符合零校准契约，成本很低，却能直接回答 Cho 的不利结果是否来自共享本身。你在内部已做过同类设计（Q9-E002 fixed-schedule，第 157 行），把它延伸到外部即可。
2. 若不补实验，则把标题/摘要/结论的因果措辞改为对"完整管线"的描述，例如标题改为 "…and no consistent advantage of complete shared mu/beta pipelines in external binary transfer"，并在 Cho 结果句同句注明时长混杂。

### 一处被埋没的可操作结论（MINOR，建议在 Discussion 点明）

Table 4 显示 "Broad, fixed 20" = 43.99%，"EEGNet, mean rank" = 42.67%，"EEGNet, mean loss" = 33.72%；即**固定训练 20 epoch 与 mean-rank 相当、且明显优于 mean-loss**。第 299 行的 matched-runtime 对照（fixed 43.99 vs historical CE 33.92，中位数 −0.174，4 人改善/5 人变差）也支持这一点。

论文目前的表述停留在"收益集中、规则非通用"。建议在 Discussion 直接给出实践结论：**"在该基准上，若算力允许，一个固定的充足时长（20 epoch）即可匹配或超过两种选择规则；时长选择审计的主要价值在于诊断表面崩溃，而非提供更优的选择规则。"** 这会让审计的落点更清晰。

### 过度声明与失败案例

未发现 "comprehensive/extensive" 式空话，也未发现需要核实的 "first" 断言；"state-of-the-art" 仅出现 1 次且用于否定（第 439 行 "the results support no state-of-the-art claim"）。失败案例与局限（第 453–467 页）谈得充分，这是论文的长处。

---

## 四、第三层：新颖性与学术价值（含文献核查）

用学术检索核对了三组关键词（cross-subject MI domain generalization、multi-band shared EEGNet、epoch/duration model selection），并对"按验证折做秩聚合选 epoch"单独检索——**未发现与该 mean-rank 做法完全相同的已有工作**，该小方法有一定新意；论文将其定位为审计工具而非新算法，是恰当的。

论文选题处于一个**拥挤但仍有真实缝隙**的方向：多数工作追求新的 DG/适配算法与更高分数，本文以"审计 + 冻结 + 保留不利/零结果"切入，定位差异化，与 PLOS ONE"方法可靠即可、不看新颖性/影响力"的录用标准匹配，**期刊选择合理**。

### M5（MAJOR）6 篇高度相关工作未被引用

以下工作与论文主题直接重合，且都不在 28 篇参考文献中，建议补入 Related Work 并说明差异轴（作用对象/机制/输入粒度）：

| 工作 | 与本文的关系 | 链接 |
|---|---|---|
| Roots, Muhammad & Muhammad (2020), *Computers*，"Fusion CNN for Cross-Subject EEG MI Classification" | 多分支 EEGNet Fusion，**在与你相同的 PhysioNet/eegmmidb 上做跨被试**，同时涉及多分支融合与计算成本，是最直接的对照 | https://mdpi-res.com/d_attachment/computers/computers-09-00072/article_deploy/computers-09-00072.pdf |
| Smedemark-Margulies et al. (2023)，"Stabilizing Subject Transfer in EEG Classification with Divergence Estimation" | 直接研究**零样本跨被试迁移与早停/训练时长正则**，正落在你第一个问题（时长选择）的交叉点 | https://arxiv.org/pdf/2310.08762 |
| Luo et al. (2023), *BioData Mining*，"Overlapping filter bank CNN for multisubject multicategory MI" | **多被试、多频带 CNN**，与你评估的 shared 多频带输入直接对应 | https://link.springer.com/content/pdf/10.1186/s13040-023-00336-y.pdf |
| Zhang, Robinson, Lee & Guan (2021), *Neural Networks*，"Adaptive transfer learning for EEG MI with deep CNN" | 高引的跨被试/适配结果，**使用的正是 Lee2019（OpenBMI）数据** | https://personal.ntu.edu.sg/ctguan/Publications/2021_Kaishuo_NN.pdf |
| Sonntag et al. (2025), *Front Hum Neurosci*，"Neurophysiological predictors of deep-learning based unilateral upper limb MI classification" | 做**神经生理特征与分类准确率的关联**，与你的 Q16 平行，是生理部分最该对话的工作 | https://pmc.ncbi.nlm.nih.gov/articles/PMC12272612/pdf/fnhum-19-1617748.pdf |
| Wei et al. (2022), *PMLR*，"2021 BEETL Competition" | **跨被试、跨数据集**的 MI 迁移基准，支撑你多数据集评估的框架定位 | https://proceedings.mlr.press/v176/wei22a/wei22a.pdf |

另有 Bria et al., Sinc-EEGNet（可学习带通，https://arxiv.org/pdf/2101.10846）可作为频段讨论的次要补充。

说明：上表仅依据检索元数据判断"是否存在、是否同题"，未引用这些工作的具体实验数字；引用时请你核对原文。

### M7（MAJOR）外部分数缺少与已发表跨被试结果的对照定位

读者目前无法判断你的 PhysioNet ~62%、Cho ~59%、Lee ~66% 在文献中处于什么位置。补入 M5 文献后，建议加一小段，把你的完整管线分数与已发表的跨被试/融合结果对照，并**用你已有的公平性表（Table 3）说明协议差异**（montage、crop、reference、时长、信息预算不同，故不可直接排名）。这样既定位了结果，又守住了"不做 SOTA 排名"的立场。

影响面：若结论成立，本文的主要受益者是做跨被试 MI 评估的研究者——它提供了一套可审计的评估/诊断范式和一个"共享多频带无一致优势"的反例；影响面不算大但真实，符合 PLOS ONE 的定位。

---

## 五、第四层：写作与语言

### M4（MAJOR）正文充斥内部实验编号（Q4–Q16、P2–P4）

这些是你实验室内部的运行编号，对读者没有意义，却出现在正文数十处，甚至进入小节标题：
- 第 185 行："### Earlier Binary Source Freeze and PhysioNet Evaluation (Q14)"
- 第 193 行："### Frozen Cho2017/Lee2019 Transfer (Q15)"
- 第 205 行："### BNCI-only Physiological Signal Characterization (Q16)"

读感像实验记录节选。**修法**：小节标题与正文改用描述性名称（如"PhysioNet external evaluation""Cho/Lee external transfer""BNCI signal characterization"）；在附录放一张"内部编号 ↔ 论文章节/数据文件"对照表（S1 Data 已有清单可复用），正文仅保留描述名。

### M6（MAJOR）摘要信息失衡

摘要 241 词，符合 300 词上限，但单段塞入约 20 个数字，且**只报告了 Cho/Lee 的 Holm p（0.000100、0.604），却未给 PhysioNet 的符号检验 p（0.06446，第 343 行）**，三个队列的统计呈现不一致。

**修法**：按"问题—方法—结果—结论"重排为 6–8 句；三个队列要么都给点估计+区间+p，要么统一只给点估计与区间、把 p 留在正文；把数字压缩到最关键的约 10 个，篇幅控制在约 200 词。

### 其他语言项（MINOR）

- 语法整体质量高，未见冠词/主谓一致的系统性错误；时态使用合理（相关工作过去时、方法现在时）。
- 部分句子过长且多重括号限定（如第 221、195 行），建议在自然处断句。
- "The corresponding saved summary is presented in Fig/Table X" 在第 45、57、87、141、267、293、303、317、347、351、375、399 行重复十余次，建议变换措辞。
- 需要实质性语言润色时，可用姊妹技能 doubao-academic-polish。

### AI 腔与破折号（机械扫描结果）

- 正文破折号（em dash）：**0 处**；仅参考文献第 479 行标题内含一个 en dash（"2008 – Graz"），属标题原文，无需改。
- AI 腔禁词：innovative/pioneering/revolutionary/transformative/surpass/remarkable/unprecedented/breakthrough/notably/underscore/"pave the way"/"stems from"/comprehensive/extensive 均为 **0**；"superiority" 2 次、"yields" 2 次，均用于中性/否定语境（第 259、343、113、195 行），无需处理。

---

## 六、第五层：图表与格式

### 优点（符合规范）

- 6 张主图均为 **TIFF、600 dpi、flattened RGB、LZW、单页、<10 MB**，宽度 6.68–19.05 cm、高度 ≤22.23 cm，文字 Arial 8–12 pt，**符合 PLOS 图表规范**；FigureSources 另备 SVG 矢量源。
- 多处采用**形状+颜色双重编码**：Fig 2（圆/方/三角）、Fig 5（圆/三角/方块）、Fig S2（圆/三角），对色盲友好；机会水平用虚线标出（Fig 2B、Fig 4A、Fig 5A）。
- 图题信息完整、可脱离正文阅读，且首句点出图意；未见 3D 柱、阴影、重网格等图表垃圾。
- 投稿稿为 DOCX、双倍行距、单栏、连续行号，标题 118 字符（≤250）、短标题 79 字符（≤100），均合规。

### 打磨项（MINOR）

1. **Fig 6 A–D 地形图使用红–蓝发散色带**，未做色盲核查；建议换色盲安全的发散色带，或为正负值加等值线/底纹第二重编码。当前效应很小、图面近乎空白——这是如实呈现，但建议在图题中明确"固定 ±6 dB 量程意在显示效应量级之小"（第 407 行已部分说明，可再点一句）。
2. **Fig 2 成稿高度仅 5.27 cm、横跨三面板**，请在 DOCX 实际摆放后核对刻度文字不小于 8 pt。
3. Fig S1 热力图为红–蓝配色，但单元格内已标注数值（第二重编码，好）；仍建议核对色盲安全色带。
4. 编号公式（BA、Selected epoch、Shared prediction）建议在正文中各做一次显式引用确认。

---

## 七、伦理与投稿行政（作者需亲自完成）

- **伦理**：第 237 行作者自行判断"二次分析无需批准或豁免"，但无机构认定文件。PLOS 对公开、去标识数据的二次分析通常可接受，但请准备好该判断的**依据**（各数据许可条款、去标识情况）以备编辑索取；Human Participants Checklist 已按 Methods 第 470–487 行填好。此项为 MINOR/作者动作。
- **ORCID**：公开档案的 given/family 姓名字段当前颠倒（应为 Ziyuan/Zhu），投稿前需更正并在投稿门户关联 iD。
- **Lee 的等价性**：你已正确说明"无显著差异 ≠ 等价"。若希望把 Lee 写成等价，可补一个预先给定界值的 TOST（可选，MINOR）。
- 数据/代码可得性、AI 协助披露（GPT-6/Codex，AI 不署名）均符合 PLOS 要求；S1 Data 提供预测与字节级来源，复现性是本文突出优点。

---

## 八、问题清单与投稿建议

### CRITICAL（足以拒稿）
- 暂无；**但 M1 若无法排除 CSP 实现错误，即升级为 CRITICAL**。

### MAJOR（一审会被点）
- M1 外部 CSP 单类崩溃需诊断（Table 7；第 397 行）。
- M2 Cho 显著结果受 14/19 epoch 混杂，需固定时长外部对比或修改标题（第 43、199、441 行）。
- M3 引言补明确贡献清单（第 21、31 行）。
- M4 去除正文内部编号 Q/P，改用描述性名称（第 185、193、205 行等）。
- M5 补 6 篇高度相关参考文献（见上表）。
- M6 摘要重排、统一三队列统计呈现（第 11 行）。
- M7 补外部分数与已发表结果的对照定位。

### MINOR（打磨级）
- 点明"固定 20 epoch 匹配/超过选择规则"的实践结论；Fig 6/Fig S1 色盲安全核查；Fig 2 成稿字号核对；长句断句；重复措辞替换；伦理依据准备；ORCID 字段更正；可选 TOST。

### 结论

**核心工作可靠、证据纪律出色、复现性强，PLOS ONE 是合适的归宿。** 建议用约 3–5 天完成：两项只做推理的补充分析（M1 诊断、M2 固定时长外部对比）+ 文献补全（M5/M7）+ 引言/摘要/编号的编辑性修订（M3/M4/M6）。完成后即可投稿；这些修改不改变你的冻结科学结论，也不需要任何新的目标拟合。
