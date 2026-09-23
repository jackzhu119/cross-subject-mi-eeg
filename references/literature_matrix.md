# 文献矩阵：跨被试运动想象 EEG（初轮全文核查）

更新：2026-09-23。目的是检查研究问题和实验协议；这不是系统综述或穷尽检索。优先记录作者全文、出版方全文、官方文档。不同任务、目标信息预算和指标的数字不可直接排序。

| 文献 | 数据、类别与划分 | 预处理、特征与模型 | 报告指标与核心证据 | 对本项目的判断与局限 |
|---|---|---|---|---|
| [Ang 等，2012，FBCSP](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2012.00039/full) | BCI IV 2a 九人四类、2b 二类；主要为同人训练/测试会话，并非九人 LOSO | 九个 4 Hz 频带、CSP、互信息选特征、朴素贝叶斯 Parzen window；论文采用因果滤波设置 | 2a 的四类 Cohen κ 约 0.57，**不是**四类准确率或跨被试 BA | 滤波器组是成熟基线；本文 Q4 的 Butterworth、MNE 多类 CSP、LDA 和离线滤波均非原论文的精确复现。 |
| [Lawhern 等，2018，EEGNet](https://arxiv.org/pdf/1611.08024) | 包括 BCI IV 2a 四类；全文 §2.3 的跨被试设计在目标受试者测试会话评估，目标训练会话不用于拟合，源受试者还分训练/验证，多次重采样 | 4–40 Hz 后的 EEG，轻量时空卷积；早期频率卷积和空间深度卷积具有滤波器组类比 | 论文展示跨被试结果，但与本项目两会话合并目标的 LOSO 不同，不搬运图中读数 | 深度比较应记录目标试次、受试者验证与多随机种子；不能把 EEGNet 或“先频率后空间”称为新方法。 |
| [He 与 Wu，2020，Euclidean Alignment](https://arxiv.org/html/1808.05464) | 2a 左右手二类；使用目标受试者的**无标签**数据做对齐，是无监督目标域适应 | 8–30 Hz，受试者均值协方差白化，再 CSP/LDA 等 | 全文 Table I 给出一个 CSP/LDA 例子 67.75%→73.53% accuracy；并非本项目 source-only 四类结果 | 目标域协方差虽不用标签，仍利用目标数据集整体分布；必须另列“有目标无标签适应”协议。 |
| [Wang 等，2023，CSP+PSD 与实例迁移](https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2023.1175399/full) | BCI IV 2a/2b；源域、目标域和迁移权重参与流程，需逐表核查目标监督预算 | 明确将 CSP 与 PSD 联合，并比较 CSP、PSD、CSP+PSD、KMM、TrAdaBoost | 文中 2a CSP+PSD+SVM 73.2% accuracy；这**不是**本项目 LOSO 四类可比基准 | 直接否定“首次融合 CSP 和 PSD”的创新叙述。原文的目标域参与和试次定义尚需逐项复核，暂不列为严格 source-only 参照。 |
| [CTNet，2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11364810/) | BCI IV 2a 四类，论文 Table 4 单列跨被试；其其他表的同人协议不同 | 卷积与 Transformer 混合 | Table 4 跨被试平均 accuracy 58.64%，该表 DeepConvNet 高 1.51 个百分点；不等于稳定优于传统方法 | 一篇论文内部也存在模型排名变化；复现时应只比同一目标预算、epoch、标签和指标。此项目目前不增加 Transformer。 |
| [MOABB 基准，2024 作者预印本](https://arxiv.org/pdf/2404.15319) · [官方结果](https://moabb.neurotechx.com/docs/paper_results.html) | 多数据集，文中主要为被试内部五折，内部三折调参；跨被试不是该基准主分析 | 多种传统与深度流水线；二类常用 AUC、多类 accuracy | 表中某个 BNCI 分数不能当作本项目 LOSO BA；深度与传统调参配置也有公平性限制 | 对代码规范和强基线有价值，对严格四类 source-only 数字参照有限。 |
| [Del Pup 等，2025，预处理比较](https://arxiv.org/html/2411.18392v1) | 六任务含 EEGMMI 左右手想象；并非 BNCI 2a；多受试者分组和嵌套验证 | Raw、最低限滤波、ICA、ICA+ASR × EEGNet 等四网络；总 4800 次训练 | 最低限预处理常优于复杂去伪迹，结果随任务和模型改变 | 直接提醒“去掉更多干扰一定提升跨人分类”是待检验假说；其每记录预处理可能利用目标记录统计，不能等同我们的源拟合 EOG 回归。 |
| [Zheng 等，2025，Domain Generalization](https://www.mdpi.com/2306-5354/12/5/495) | BCI IV 2a 四类九人 LOSO，两会话；另 KU54 二类；作者主张不使用目标数据训练 | 多频带教师/学生、源域 CORAL 对齐、特征分离 | 2a 60.07±11.86% accuracy；其源内 80/20 验证是否 subject-disjoint 与参数选择嵌套性不够明确 | 说明 2025 年已有多频带严格跨人研究。本项目需要清楚注明目标信息预算，未来与其指标接近时也不可仅凭平均数声称优势。 |
| [Habashi 等，2025，TFOC-Net 作者预印本](https://arxiv.org/pdf/2507.02510) | 四个数据集；BCI IV 2a **只取左右手二类和 C3/Cz/C4 三通道**，按受试者 LOSO | 短时傅里叶变换 STFT 输入 CNN，比较窗口重叠和训练批次的受试者平衡 | 论文报告 IV-2a 65.96±6.14% accuracy；这是**二类**，不可与本项目四类数字比 | 直接证明“用 Fourier/STFT 处理跨被试 MI”已有先例；其 2025 作者版全文 §2.2/2.6、Table 5 核对了任务与划分。 |
| [Brookshire 等，2024，EEG 泄漏审计](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2024.1373515/full) | 非 MI 的临床 EEG 任务；比较随机片段和按受试者拆分 | 深度学习泄漏分析 | 分段随机分割和受试者分割差距明显，属于方法警示而非 MI 成绩 | 受试者是外层测试单位；所有监督和数据驱动变换都需明确拟合边界。 |

## 文献核查记录与待核问题

- 检索线索：`BCI Competition IV 2a FBCSP original`、`EEGNet cross subject validation`、`CSP PSD joint feature motor imagery 2023`、`four class LOSO domain generalization MI EEG 2024 2025`、`EEG preprocessing artifact removal nested subject split`。先核对全文方法和表，再对照 DOI/出版页；这轮不是按 PRISMA 进行的系统筛选。
- 上述 2012、2018、2020 方法文献用于**定义对照**；2023–2025 文献用于初步检查新颖性和协议。部分期刊网页在本轮复查时限流，已读取作者版、开放全文或搜索缓存；因此原论文的每项目标监督预算和各表确切训练组成仍标为待复核，不据此给本项目排名。
- 尚需补充：2024–2026 其他 four-class source-only LOSO 原论文、跨数据集验证、伪迹强度与神经保真评价的原始工作。文献空白不能仅凭这个矩阵宣称存在。
- 对于任意成绩，必须同时记录 `类别数 × 目标试次 × 源/目标训练信息 × 采样窗 × 会话组成 × artifact 政策 × 评价指标` 后才可比较。

## 当前可检验研究缺口（假说，而非“首次”主张）

在**固定 source-only 四类 LOSO、相同目标试次和相同源内调参预算**下，检验频带空间表示、频谱表示及伪迹抑制对不同受试者的稳定性，并同时核对分类表现、伪迹敏感性和感觉运动信息保真。已有 CSP+PSD 和多频带方法，因此贡献若成立，应来自控制充分的泛化与机制分析，且需要外部数据集确认。当前证据不足以声称新的算法、新的去干扰机制或可投稿成果。
