# 论文1：面向学校 HPC 的方法升级与文献依据

核查日期：2026-10-23。本文是新实验的研究设计说明；没有启动训练、生成新的效应量或改变既有论文与冻结结果。执行配置、数据清单和代码负责确定实际输入与训练细节。本文件与它们一起固定后再开始本版本训练。

## 1. 本次值得验证的贡献

本轮的中心问题是：**在保持源数据、网络、训练时长和推理路径一致时，按“参与者×类别”控制源训练尾部损失，能否提高未见参与者的较弱类召回率；同试次的频带一致性是否带来独立增益？** 这是一个可以被对照和消融否定的问题，能够把方法贡献与已有扩源收益区分开。

已有 eligible-v3 结果为该问题提供动机。冻结的 BROAD / tail_min_recall 比较中，S60 相对 S9 的 Dreyer 较弱类召回率提高 21.1667 个百分点，95% 配对 t 区间为 [17.1226, 25.2107]；固定时长对照也是已有独立材料的一部分。这些结果属于旧扩源实验，不能转记为本次损失函数的成绩。原结果同时没有建立 S60 优于 S29、或 tail_min_recall 选轮优于 mean_ba 的证据。因此，本轮保持 S60 输入规模不变，直接比较训练目标，避免再次以增加源数据代替方法检验。原数值来源：[冻结结果说明](../ELIGIBLE_V3_RESULTS_20261018/RESULTS_REVIEW_zh.md)及其链接的独立审计。

本轮可形成三项明确贡献，是否得到性能支持要由完整结果决定：

1. **面向参与者内类别失衡的源训练目标。** 训练关注源参与者×类别组，而报告终点是未见参与者的较弱类召回率，并同步报告平衡准确率。这使所优化的风险单位与所关心的使用者表现更接近。
2. **风险项与频带项的受控拆分。** 五种方法使用同一骨干、相同三视图前向与 BatchNorm 暴露、相同训练采样及 broad-only 推理，单独检验尾部项、一致性项和二者组合；以既有 GroupDRO 为直接稳健风险对照。
3. **选择与评估的分离。** 源内固定 inner 验证选择时长，outer 参与者只评分；外部主比较固定 40 轮，source-selected 检查点作为次比较。两套外评复用相同最终训练轨迹，能够区分训练目标差异与选轮差异。

这些贡献是方法与评估设计的组合，不构成新的 CVaR 理论、普遍校准免除、临床有效性或现有 DG 方法全面优越性的主张。新训练完成后，应把获得支持的效应量放在摘要和引言贡献段前列；完整对照及其不确定性仍须保留在结果表中。

## 2. 已核实的直接相关文献

本次采用四篇 2025–2026 年正式 MI-EEG DG 论文及两篇方法基础论文。检索覆盖 2024–2026；两篇 IEEE 论文的 DOI 含 2024，但正式卷期在 2025，不能把 DOI 中的年份直接当作卷期年份。完整作者、DOI、核查范围和出处见 [references.json](references.json)。这是一轮针对性查新，不是系统综述或“首次”证明。

| 文献 | 已有方法及与本项目的关系 | 本轮应当比较或说明的差别 |
|---|---|---|
| Zhi 等，SCLDGN，IEEE TBME，2025 [1] | 监督对比学习与相关对齐用于跨被试运动解码的 DG。 | source-only、类别判别与域不变表示已有先例。本轮重点是参与者×类别尾部终点和受控消融。 |
| Zhong 等，EEG-DG，IEEE JBHI，2025 [2] | 多源 MI EEG 的边缘与条件分布对齐，面向未见目标。 | 不能将“不用目标适配”本身作为新算法。本轮没有复现其原模型，因此不能报告与 EEG-DG 的直接性能优劣。 |
| Chen 等，MI-DGHCL，Expert Systems with Applications，2026 [3] | MI EEG DG 中结合特征一致性与双曲对比学习。 | 一致性和不变性并非本项目独有。本轮采用紧凑模型，检验具体尾部风险机制的增量，而非堆叠更大架构。 |
| Zheng 等，Bioengineering，2025 [4] | 频谱知识蒸馏、相关对齐和距离正则化用于跨被试 MI DG。 | 与频带知识利用直接相关；本轮的三视图预测一致性不能被称为首次频谱 DG。 |
| Sagawa 等，GroupDRO，ICLR，2020 [5] | 预定义组的最坏组风险优化，强调正则化与早停对泛化的重要性。 | 提供直接稳健风险基线；小组高损失也可能是噪声，尾部项并不自动改善泛化。 |
| Rockafellar 与 Uryasev，CVaR，2000 [6] | 条件风险价值及其优化的基础工作。 | minibatch 上的组 top-k 平均是有限样本尾部代理，不是新的风险理论或总体最坏风险保证。 |

核查以 publisher-deposited Crossref、正式会议页、PubMed 及作者预印本为主。IEEE/Elsevier/MDPI 部分直接页面出现机器人验证、403 或限流，本次没有绕过；对应条目只据元数据及可见原始摘要描述方法，不声称已读其完整正文、超参数或代码。GroupDRO 的 DOI 指向作者预印本，明确不冒充 ICLR 会议 DOI。不能把论文中作者自报的 SOTA 表述直接转述为本项目结论。

## 3. 固定候选方法与最小对照

### 3.1 输入、组和采样

使用当前 eligible-v3 已定义的 BNCI+Yang 源参与者、资格规则和信号输入；本轮的新方法目录不覆盖旧科学输入。参与者 ID 必须以 cohort 为命名空间，组定义为 `g = (cohort, participant, class)`。训练 sampler 按 cohort、参与者、类别平衡，所有五个方法共享相同 sampler 及对应随机种子。采样平衡与损失加权是不同操作，须同时在配置中保存。

同一试次产生 broad、mu、beta 三个冻结视图。所有方法使用相同的三视图前向调用与顺序，即使其一致性系数为零，也保留相同的 BatchNorm 训练暴露。推理统一使用 broad 视图、`eval()` 模式；不以外部目标统计量重新拟合归一化、更新 BatchNorm 或挑选视图。对目标事件/类别元数据作冻结映射与评分不等于允许目标拟合。

### 3.2 目标函数的含义

令每个当前 minibatch 中已观测组的 broad 监督交叉熵均值为 `ell_g`；`L_mean` 为相同组定义下的基线均值。尾部项取损失最大的 `ceil(tau × G)` 个已观测组的均值 `L_tail`，其中 `G` 是当前 batch 的已观测组数，`tau = 0.5` 表示**上半部分损失组的比例**，而不是另一个符号约定下的置信度。缺失组不得以零损失填充。

组合目标为：

`L = (1 − lambda_tail) × L_mean + lambda_tail × L_tail + lambda_JS × JS(p_broad, p_mu, p_beta)`

`lambda_tail = 0.5`，`lambda_JS = 0.1`；代码键 `tail_fraction = 0.5` 对应上述 tau，不是 softmax temperature。JS 使用同一试次、温度1的三视图 softmax 概率，以三者平均概率为混合分布，计算各视图 KL 后平均视图和试次；三个分支均保留梯度，没有 stop-gradient teacher。以上是开跑前固定的工程候选值，没有经 Dreyer 或本轮结果优化，不得在结果出现后更改。

该公式针对 batch 中观测到的组，不等同于对全体源参与者的精确总体 CVaR。若实现采用组 EMA、非均匀 cohort 权重或不同的风险聚合，须在本版本开跑前同步写入配置与此定义；不能在训练恢复时悄悄换目标。所有额外优化状态都属于断点状态。

| 方法 ID | 损失 | 作用 |
|---|---|---|
| `erm` | 平衡采样下的 `L_mean` | 主基线；不是未平衡自然分布 ERM。 |
| `groupdro` | 相同 source 组上的 GroupDRO 加权损失 | 检查增益是否只是既有组稳健优化的普遍效果。 |
| `tail` | `0.5 L_mean + 0.5 L_tail` | 尾部项独立消融。 |
| `consistency` | `L_mean + 0.1 JS` | 频带项独立消融。 |
| `tail_consistency` | `0.5 L_mean + 0.5 L_tail + 0.1 JS` | 预先指定的候选组合方法。 |

使用同一 EEGNet 式紧凑骨干、优化器、更新预算、训练数据、初始化种子及三视图调用。准确名称应为该实现的 EEGNet 式骨干；不因名称相似就声称逐行复现原始 EEGNet。GroupDRO 的权重更新参数 `eta=0.01` 同样提前固定；它是本项目统一骨干下的实现，不宣称与原论文任务和最优配置完全等同。

GroupDRO 的初始组权重为 `q0_g = 1/(C × 2 × N_cohort)`，与 cohort-balanced 训练采样的名义权重对应。生产批次在每个 cohort 内不放回抽4人，因此组包含概率 `pi_g = 4/N_cohort`；合成小样本检查如需放回，则使用 `pi_g = 1 − (1 − 1/N_cohort)^4`。模型损失采用当前抽样之前的全体组权重 `sum_observed(q_old_g × ell_g/pi_g)`，组权重按 `ell_g/pi_g` 做指数更新并在全组归一化。这样不把少人 cohort 更频繁的抽样误当成更大组风险；不对当前已观测组再次条件归一化。q、包含概率和初始权重均随断点保存。这是 sampling-frequency correction：BatchNorm 的当前批统计使组损失依赖 batch context，不能由固定损失的包含概率恒等式推导出实际神经训练对全数据 minimax 目标严格无偏或收敛的保证。DRO 与尾部项是不同的已定义目标，比较检验其泛化效果，并不假定两者相同。

不在本轮扩充神经方法数。文献中的 SCLDGN/EEG-DG 是明确相关工作，尚未纳入直接算法基准，因此本轮最多支持“在预定五方法比较中”的结论。若投稿要求与更多 DG 算法直接对照，应作为后续独立版本预先固定，而不是看到当前目标结果后再补选有利对手。

## 4. 固定 90 条轨迹的源选择与外评

### 4.1 开发阶段：75 条

五方法 × 五个固定 outer participant folds × 三个冻结种子，共 **75 条开发训练轨迹**。同一人的全部会话/试次只能落入一个 outer 角色。每个 outer 训练池内，再固定 cohort 分层的 inner 验证参与者；这些人不参加该条轨迹的参数拟合。inner 用于每轮评分和选轮，outer 人只用于评分，不能兼作 checkpoint 选择人。

source-only 选轮指标先在每个 inner 验证参与者计算 `W_s = min(recall_s,left, recall_s,right)`，再在每个 cohort 内均人、两个 cohort 间等权。并列时选更早一轮。它不是把 BNCI 与 Yang 的全部验证人直接等权池化，也不先合并试次。代码保存各轮 per-person 值及 `source_equal_cohort_mean_min_recall` 曲线，便于复核。outer 源内主汇总采用同样的 cohort→person 权重；Dreyer 外部只有一个 cohort，按参与者等权。

首批可以只运行一个 outer fold 的 15 条，用于尽快得到运行时间和初步开发曲线；该批仍是正式矩阵的一部分，不重复拟合。但它不是整个研究，也不据此删方法、换系数或修改种子。余下轨迹由同一任务清单补齐。

### 4.2 最终源训练：15 条，两个评估检查点

五方法 × 三个种子，共 **15 条最终源训练轨迹**。每条最终轨迹固定训练至第 40 轮，保留第40轮和预先选定轮的模型，并维持最近两代可恢复训练断点；无需为全部40轮分别保存完整优化器：

- **外部主要展示比较：固定 40 轮模型，探索性。** 五方法共享时长，隔离选轮时长差异。
- **次外部比较：source-selected 模型，探索性。** 每个方法取五 outer folds × 三种子共15个 inner 最佳轮的整数中位数，不超过40；从同一最终轨迹取该轮 checkpoint，无须重训。

最终选择冻结在外部目标评分之前。开发 outer 成绩、Dreyer 标签或外部曲线均不能用来确定最终时长。15个 inner 选择的中位数及其完整来源保存在 `state/selection.json`；所有源曲线完整保留，而非只保留获选轮次。

合计 **90 条神经训练轨迹**；两套外评 checkpoint 不把轨迹数翻倍。运行修复可恢复同一轨迹，改变损失函数、数据资格或时长规则则需要新的实验版本。三种种子不等于三倍独立参与者样本量。

## 5. 可证伪假设、统计单位及完整报告

**唯一主方法检验**为 nested outer-source 的 `tail_consistency − erm`，主终点为逐人较弱类召回率 `W`，cohort 间等权、cohort 内均人。各 outer 模型的时长仅由其 inner 源验证选择。Dreyer 的 fixed40 及 source-selected 域均明确为探索性，不把 fixed40 的“主要展示比较”写成未见外部确认检验。同步报告平衡准确率 `BA = (recall_left + recall_right)/2` 和两类召回率，以检查提高弱类是否以明显损失另一类为代价。不能仅因 W 上升就称所有解码性能全面改善。

**预定次对比**为组合方法对 GroupDRO、tail-only、consistency-only 的 W 差值，以及组合方法对 ERM 的 BA 差值，共四项；它们用于判断是否超出通用组稳健学习、组合是否具有独立增量及总体识别能力的变化。四项在各评价域内构成单独预定家族，作 Holm 校正；没有跨三个评价域择取最小 p 值的全局优越性检验。对于 `full − tail − consistency + erm`，只能在预先指定同一终点和分析规则时称为交互作用检验；否则它是描述性分解，不能凭组合方法最高就宣称协同。

每位参与者、每个种子分别算 W/BA，再对该参与者的三种子指标平均，得到每人一个配对差值。源内效应按 cohort→person 等权，bootstrap 在各 cohort 内按人配对抽样；外部按人配对抽样。代码对差值进行双侧 sign-flip 检验；n≤16时全枚举，否则固定种子 Monte Carlo 并作 plus-one 修正，该检验仍依赖符号可交换性。报告人数、试次数、效应量和点态95%区间；不把 seed×trial 展开后当独立重复。外部参与者配对 bootstrap 反映当前训练协议和拟合集合条件下的参与者不确定性，不能替代新源队列、新种子或新实验室的独立重复。

outer cross-validation 的训练集相互重叠，不能把五个 fold 当五次独立实验；person bootstrap 也不能消除共同拟合导致的相关性。因此源内结果是受控开发验证，Dreyer 是已有暴露背景下的探索性外部评估。保留所有五方法、固定40和source-selected两套完整表，不挑选其中最好的一套作为唯一结果。

本轮所有 λ、τ 和方法集合均固定，不开展目标驱动超参数搜索。训练失败须保留失败状态；不把缺失方法的结果填成零，也不只保留成功或正向种子。

## 6. Dreyer 的角色与更高层次证据

Dreyer 已有大量历史评分，不能作为新算法的完全未见确认集。它可用于检验本版本在相同外部任务上的迁移表现，但当前方法设计已知旧研究发现，仍属于探索性。已经在 Q14/Q15 使用的 PhysioNet、Cho2017 或 Lee2019，也不能仅改称“新数据”就成为未接触过的确认集。

若目标是支持更强的跨队列有效性，需要在本轮结果不用于调参的前提下，另选此前未使用的独立 MI 队列或前瞻性采集。先冻结数据资格、事件映射、通道、时窗、标签、最终模型及唯一主终点，再读取其结果；这一扩展不包含在当前 90 条轨迹中。没有该证据时，论文仍可报告受控方法检验和探索性外部迁移，但不能声称普遍优越或临床可用。

## 7. 预定图表与论文写法

下列图表由本轮完整保存的预测、source 曲线及训练日志生成；当前尚无本轮数值，不生成示意数据冒充结果。

| 图表 | 核心内容 | 支持的判断 |
|---|---|---|
| 主效应图 | 五方法 W 与 BA；个人配对差值和95%区间；源内主分析与固定40探索性外评分面 | 候选方法是否提高弱类，同时保留总体识别能力。 |
| 个人异质性图 | 全体参与者的 W/BA 变化、两类召回率变化，按预定身份排序 | 均值收益是否广泛，还是由少数人或一类驱动。 |
| 消融图 | `full−ERM`、`full−GroupDRO`、`full−tail`、`full−consistency` | 组合是否带来超出各部分的实测增量。 |
| 选轮图 | inner source 曲线、选中轮次及固定40/所选轮的外评差值 | 训练目标和时长选择各自的贡献。 |
| 计算与完整性表 | 75+15任务状态、实际更新数、时间、峰值显存、恢复次数 | 比较资源是否匹配，恢复是否避免重复训练。 |

能够先写入引言的贡献段应使用设计层面的准确表述：

> We test a source-only training objective that combines participant-by-class tail-risk regularization with within-trial spectral consistency. A matched five-method study separates the two components from balanced empirical risk minimization and group distributionally robust optimization. Participant-disjoint source validation and fixed-duration external comparisons distinguish objective-level effects from checkpoint-selection effects, while participant-level endpoints quantify both weaker-class recall and balanced accuracy.

完成全部实验后，用确切效应量替换“test”等设计性措辞。若组合没有超过某个直接基线，贡献可以是识别有效成分及其适用边界，不能改成该基线未测或从表中删除。以简洁具体的结果减少冗余防御性句子，不能以省略不利对照来制造优势。

## References

1. Zhi H, Yu T, Gu Z, Lin Z, Che L, Li Y, Yu Z. Supervised Contrastive Learning-Based Domain Generalization Network for Cross-Subject Motor Decoding. *IEEE Transactions on Biomedical Engineering*. 2025;72(1):401–412. [doi:10.1109/TBME.2024.3432934](https://doi.org/10.1109/TBME.2024.3432934).
2. Zhong XC, Wang Q, Liu D, Chen Z, Liao JX, Sun J, Zhang Y, Fan FL. EEG-DG: A Multi-Source Domain Generalization Framework for Motor Imagery EEG Classification. *IEEE Journal of Biomedical and Health Informatics*. 2025;29(4):2484–2495. [doi:10.1109/JBHI.2024.3431230](https://doi.org/10.1109/JBHI.2024.3431230).
3. Chen J, Pi D, Gao F, Ma C, Chen Y. MI-DGHCL: Motor imagery EEG domain generalization via hyperbolic contrastive learning. *Expert Systems with Applications*. 2026;312:131477. [doi:10.1016/j.eswa.2026.131477](https://doi.org/10.1016/j.eswa.2026.131477).
4. Zheng Y, Wu S, Chen J, Yao Q, Zheng S. Cross-Subject Motor Imagery Electroencephalogram Decoding with Domain Generalization. *Bioengineering*. 2025;12(5):495. [doi:10.3390/bioengineering12050495](https://doi.org/10.3390/bioengineering12050495).
5. Sagawa S, Koh PW, Hashimoto TB, Liang P. Distributionally Robust Neural Networks for Group Shifts: On the Importance of Regularization for Worst-Case Generalization. *International Conference on Learning Representations*. 2020. [Official conference page](https://iclr.cc/virtual_2020/poster_ryxGuJrFvS.html); [author preprint, doi:10.48550/arXiv.1911.08731](https://arxiv.org/abs/1911.08731). The DOI is for the preprint, not a conference DOI.
6. Rockafellar RT, Uryasev S. Optimization of conditional value-at-risk. *The Journal of Risk*. 2000;2(3):21–41. [doi:10.21314/JOR.2000.038](https://doi.org/10.21314/JOR.2000.038).
