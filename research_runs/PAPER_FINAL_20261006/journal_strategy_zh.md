# 当前稿件的 SCI 投稿策略

本版修订日期：2026-10-07；官方期刊页面核验日期：2026-10-05。作者：Ziyuan Zhu；通讯邮箱：zzy2630816871@gmail.com。学院英文名采用发表论文单位中已核对的 College of Artificial Intelligence Medicine；尚未获得可访问的校方英文命名页面，最终署名请作者确认。

**主推荐首投 Journal of Neural Engineering（JNE）；现实备投顺序为 Scientific Reports → PLOS ONE。IEEE TNSRE 可作为接受较高编辑拒稿风险时的条件性冲刺。** 这个顺序依据本文现有贡献与期刊范围，不是按未经核验的影响因子排列。本文不填写未核验的 JCR 年份、影响因子、JCR 分区或中科院分区，也不承诺录用。正式投稿当天应以 Clarivate Master Journal List/JCR 和本单位当年的认可口径复核收录与分区；出版社展示的未注明年份“Impact Factor”不代替指定年份的 JCR 记录。

## 1. 这篇文章可以争取的贡献

推荐将文章定位为**跨被试运动想象 EEG 的源数据模型选择诊断与固定谱共享泛化边界的实验审计**。其价值是把训练时长、参与者异质性、固定迁移协议和反例结果放在同一个可核查框架里，并用隔离的 BNCI 传感器生理描述限定模型解释的范围。论文不提出具有普适优势的新解码器。

当前可支持的重点如下：

- 内部九人 BNCI 开发集上，mean-rank 相对 mean-loss 选择的平均平衡准确率增加 8.951 个百分点，但两人贡献 87.57% 的总增益。这是已观察开发基准中的探索结果；外部实验没有检验 rank 与 loss 选择规则的差异。
- 匹配运行条件的固定 20 epoch 对照具有正平均差，但仅四人改善、五人变差，参与者中位差为负。不能写成“对大多数人均更好”。
- 固定谱共享的外部效应分别为 PhysioNet +0.573 pp、Cho2017 −1.513 pp、Lee2019 +0.204 pp。PhysioNet 与 Lee 区间包含零；Cho 的负效应经预声明的两队列 Holm 校正仍成立。应把 adverse result 写入摘要、正文和投稿信。
- 公开原始数据来源、源/推理冻结协议、参与者层面的不确定性、原始至预测验证及保存预测独立重算，支持可检查的实验结果。保存预测重算与原始 EEG/模型回放不是同一个验证层次，必须按实验分别说明。

- 本版加入明确的零校准定义和工作流程图：目标数据不参与参数拟合或模型选择，但目标标签仍用于元数据、计分及单独的生理描述。不能写成全程无标签或普适实时系统。
- Q16 BNCI 组件采用九人两会话、18 原始文件的固定窗口与 Welch 估计；通道功率比、侧化和已保存 source-LOSO 分数的关联是描述性结果。窗口/频段协议与细化估计器在新功率计算前提交，但发生在 decoder 结果已知之后，不能称为独立前瞻性预注册。它不证明网络学到了 ERD，不是外部生理复制，也未新增解码训练。
- 公平比较的边界补充说明：Q5/Q6 时长选择随 normalization 同时变化；Q14 broad/shared 18/17 epochs、Q15 14/19 epochs 是完整冻结流程比较。Q16 生理任务窗口两秒、用于关联的 Q14 decoder 窗口三秒；不能把两者解释为同一特征空间。

JNE 的领域读者更容易理解这些问题为何影响 BCI 研究；稿件已有的 MOABB 与分类综述引用也提供了领域背景。引用同一期刊论文只能说明主题关联，不能证明当前稿件达到期刊的原创性门槛。

## 2. 候选期刊与取舍

| 期刊 | 当前稿件的适配与位置 | 主要门槛及稿件动作 | 已核验官方依据 |
|---|---|---|---|
| **Journal of Neural Engineering** | **主推荐首投**。神经科学与工程交叉、BCI 基准可靠性与跨人解码是直接学科匹配；适合围绕参与者诊断和迁移限制写成原创实验研究。 | 官方要求对既有研究有显著新增，通常不接受仅增量改进。必须把审计得到的科学认识讲清，避免把代码/哈希整理本身当主要创新。保留完整负结果与外部验证，以生理描述增强解释边界；不能声称已证明普适 rank 规则或网络机制。 | [IOP/JNE 作者指南与范围](https://publishingsupport.iopscience.iop.org/journals/journal-of-neural-engineering/) |
| **IEEE Transactions on Neural Systems and Rehabilitation Engineering（TNSRE）** | **条件性冲刺**。范围包括神经系统、运动控制、康复工程及辅助设备软件；EEG 解码方法有主题关联。这里的“冲刺”指领域发表野心，不是已核验的影响因子大小比较。 | 官方要求 substantially novel methodology/technology/experimentation。本文缺少在线辅助控制、患者与康复终点，且主要是审计而非新方法，存在较高适配与创新性风险。投稿信可说明可靠评估对后续辅助 BCI 的意义，但不能创造康复效益。 | [官方投稿指南](https://www.embs.org/tnsre/for-authors/submission-guidelines/)、[作者信息](https://www.embs.org/tnsre/for-authors/) |
| **Scientific Reports** | **第一现实备投**。官方范围涵盖自然科学、医学和工程；多队列 EEG 的原始实验结果与审计适合其跨学科范围。 | 需要让非 BCI 读者理解研究问题；主文聚焦模型选择失效和谱共享限制，把长期研究历史与细节移入补充。不能靠大量公开数据替代明确的科学问题。 | [官方范围](https://www.nature.com/srep/about)、[作者指南](https://www.nature.com/srep/author-instructions/submission-guidelines) |
| **PLOS ONE** | **第二现实备投**。官方明确纳入负结果、零结果与复现研究，并按科学有效性、方法和伦理质量评估。当前 adverse/null 结果可完整保留。 | 相似或衍生研究仍须充分科学理由，否则可被拒；“做了 EEGNet 对照”本身不足。应强调受试者层面的集中收益、冻结迁移后的反例和可重复审计。完整提供数据/代码可用性与二次分析伦理说明。 | [官方范围](https://journals.plos.org/plosone/s/journal-information)、[发表标准](https://journals.plos.org/plosone/s/criteria-for-publication)、[投稿指南](https://journals.plos.org/plosone/s/submission-guidelines) |
| **Frontiers in Neuroscience — Neuroprosthetics** | **条件性备选，当前不放入默认转投链**。该专区明确包括 neuroprostheses 和 brain-machine interfaces，跨人 EEG 解码具有主题关联；Original Research 类型允许 disconfirming results。 | 当前公共数据计算研究政策要求 appropriate validation，其例举包括独立临床/患者队列或生物学验证。本文使用公开健康人 EEG 队列，不能自动把它们说成临床/患者验证，也不能把工程回放验证等同于该要求。能否满足该政策须由编辑按本文研究类型判断；因此不能将它视为无条件安全备投。 | [Neuroprosthetics 范围](https://www.frontiersin.org/journals/neuroscience/sections/neuroprosthetics/about)、[文章类型](https://www.frontiersin.org/journals/neuroscience/for-authors/article-types)、[研究方法政策](https://www.frontiersin.org/guidelines/policies-and-publication-ethics) |

Neural Networks 与 Neurocomputing 未纳入本次正式推荐：2026-10-05 的抓取尝试对 ScienceDirect/Elsevier 官方网页及作者包返回 403，无法核验其最新要求；不能用第三方网页补写“已核验”规则。就现稿的科学内容判断，其主要贡献也不是新的神经网络算法。IEEE TBME 的范围虽包含神经工程，但官方明确要求重大方法或领域进展，单纯技术正确不足；[当前作者指南](https://www.embs.org/tbme/prepare-a-manuscript/)另对 LLM 写作使用作严格限制，现有 AI 辅助起草稿不能未经核对实际使用范围而直接沿该路线提交。因此目前不优先选择这些期刊。上述未推荐并不等于永久排除。

## 3. 用现有结果完成期刊适配

**JNE 版本。** 保持当前题目中的 source-only model selection 与 limits of shared spectral representations。摘要用 Objective / Methods / Results / Conclusion 的清晰逻辑，报告负的 Cho 效应和 uncertain 的另两队列效应；IOP 当前通用说明要求摘要通常不超过 300 词。当前获取的 JNE 支持页没有建立本刊特定的硬性正文页数限制，不应编造“固定八页/十页”。LaTeX 模板在该页被写为可选。主文优先保留研究问题、明确 Related Work、Experimental Design、Statistical Analysis、隔离流程图、运行条件对照、外部冻结、参与者结果与单列 Limitations。Q16 保留固定的 μ/β 传感器描述与 n=9 关联，避免将新增图当成机制证明；长期实验编号历史和逐文件审计表移入补充。

**TNSRE 版本。** 当前官方要求 IEEE transactions 模板，常规研究稿不超过 10 页（不含参考文献），正文不小于 10pt、图表文字不小于 8pt，摘要不超过 250 词。这是研究论文，不应改名为 review paper 以套用综述页数。期刊为完全金色 OA；作者信息页列明 **2026 年提交稿件 APC 为 US$2160**，实际付款/折扣/税费以提交时官方规定为准。其投稿指南仍展示 2024/2025 旧费用，不能把旧金额当成 2026 费用。单位二次公共数据分析是否需要伦理审查/豁免，以及原始数据采集伦理与同意的正确表述，均需作者实际核实；不得为了符合表格要求捏造批准编号。

**Scientific Reports 版本。** 官方要求摘要最多 200 词且无小标题；标题不超过 20 词；建议文章不超过 11 个排版页、主文不超过 4500 词（不含摘要、Methods、参考文献、图注）。指南明确多数正文长度为建议，不能把所有建议误写为统一硬限。其允许 Methods 中记录 LLM 使用，仍由作者承担内容责任。外部队列和内部探索结果分开叙述，避免将不同二分类/四分类任务的准确率放到同一性能排行榜中。

**PLOS ONE 版本。** 沿用完整原始研究结构，按官方当前投稿指南处理标题页、摘要、数据可用性和统计报告；不将“reproducibility audit”包装成系统综述。必须说明为什么现有基准的时长选择、参与者聚合和迁移反例值得研究。若已有相近论文或本作者相关论文，应准确引用与解释新增内容。

**Frontiers 条件性版本。** Neuroprosthetics 接受 Original Research；其当前文章类型页写明最多 12,000 词，且确认反例结果可在原始研究范围内。先核查上述公共数据验证政策的适用性，再决定是否准备正式投稿格式。AI 辅助生成正文须如实在致谢披露，并按该刊政策记录工具、版本/模型、来源与用途；未知工具版本不能猜填。

## 4. 投稿前必须成立的作者声明

使用正式作者姓名 Ziyuan Zhu 和已提供邮箱 zzy2630816871@gmail.com；单位英文名称依据官方来源与作者实际隶属关系，不自行创造学院名称。资金来源、利益冲突、作者贡献、公共数据二次分析的机构要求及 AI 实际用途，应由作者核实后填入；没有机构批准材料时，不能把“作者需确认”改成“已获批准/无需伦理”。

公开数据不等于无使用限制。原始录制机构的伦理与同意、各数据源许可及使用条款，应按来源分别引用。本稿不新增受试者，也不声称提供患者利益。现有零相位滤波和离线推理没有测量在线延迟，不能写成可直接部署的实时系统。原始电压标定、Cho 采集参考和硬件 cue latency 未独立确认，适配器统一张量不等于物理测量统一。

Q14 与 Q15 使用不同源冻结和预处理；三个外部队列分别分析，不能合并成一个“215 名已确认互不重复受试者”的外部总体。三随机种子、Lee 两次会话、源子集和试次是重复测量，不能增加参与者样本量。Lee 零效应不证明等效，Cho 的负效应不证明所有频谱共享方法均有害。严谨的限制报告会减小审稿时的可反驳空间，不能被理解为保证达到任何期刊门槛。

## 5. 投稿信可使用的核心定位

> We report a participant-level experimental audit of zero-calibration motor-imagery EEG decoding, defined by the absence of target-dependent fitting or model selection. Training-duration choices produced concentrated gains in a small development benchmark, whereas fixed spectral sharing showed no consistent external advantage and reduced balanced accuracy on Cho2017. Separately frozen sensor-level physiology describes the source benchmark without being used to tune the decoders or infer their learned mechanism.

投稿信接着说明与具体期刊读者的关系，保留“不检验临床效益或在线控制”的边界。不要加入 state-of-the-art、universally calibration-free、clinically validated 或 invariant physiological mechanism 等未被本研究支持的措辞。

Q16 增强了生理解释的透明度，但九名健康被试的描述性分析不自动满足任何期刊的新颖性、临床验证或独立机制证据门槛。当前默认执行路线是把 JNE 版本完善到作者可审阅状态；收到实际编辑决定后，再按上述范围和格式修改转投。同一时间只向一个期刊正式提交；本次材料准备没有向期刊发出投稿、询问信或其他消息。官方页面的抓取日期、响应状态、文本快照、SHA-256 与所支持判断见 `evidence/journal_sources.json`。
