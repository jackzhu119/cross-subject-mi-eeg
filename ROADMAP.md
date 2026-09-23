# Research Roadmap

本路线图采用“问题 → 原理 → 方法 → 实现 → 实验 → 结果 → 解释”的推进方式。时间按掌握程度调整，不以赶进度替代阶段验收。

> 进度更新（2026-09-23）：Phase 0/1 的环境、数据审计与基础频谱图已完成；Phase 2 的左右手传统 baseline 及 Phase 3 的 CSP/Welch PSD 探索已有真实结果；源拟合 EOG 回归的二分类探索也已完成。完整四分类九人 LOSO 的 Q4-E001 与后验维数消融 Q4-A001 已完成并验证，未发现九频带方法的整体均值优势。具体数字与限制以 [四分类结果](docs/q4_e001_results.md)、[维数消融](docs/q4_a001_capacity_results.md)、[Research Progress](docs/research_progress.md) 为准。下面各阶段任务仍作为学习与投稿前验收表。

## Phase 0：研究基础设施（已完成基础；追溯加固持续进行）

**目标**：让后续每个数字都能追溯到数据、代码、参数和划分。

任务：

- 建立独立 Python 环境和依赖记录。
- 固定目录、命名规范、随机种子和输出格式。
- 建立 Research Log 与 Experiment Registry。
- 明确数据许可、引用和本地缓存位置。

验收门槛：

- 新环境能导入 MNE、MOABB、NumPy、Pandas、SciPy、scikit-learn。
- `inspect_bnci2014_001.py` 能先显示元数据，再对 Subject 1 输出真实 channel、sampling rate、annotation 和 session/run 结构。
- 不声称尚未运行的结果。

## Phase 1：EEG 与信号处理基础

**Research Question**：真实 EEG 数据如何由连续多通道信号转成可用于运动想象分析的 trial？

学习与实践：

- `Raw`、channel、channel type、sampling rate。
- event、annotation、epoch、artifact。
- Sampling / Nyquist theorem。
- band-pass、notch、FFT、PSD、基础时频图。
- 观察 C3、Cz、C4 及邻近感觉运动区通道，但不预先声称它们一定最优。

最小实验：

1. 检查 Subject 1 两个 session 的原始结构。
2. 画短段原始 EEG，并标注事件。
3. 对比滤波前后波形与 PSD。
4. 以 cue onset 为时间零点提取 epoch，核对数组形状和标签计数。
5. 明确 artifact trial 的处理规则并记录删除数量。

验收门槛：

- 能解释 channel、sampling rate、event、epoch 的区别及其数组形状。
- 能说明 250 Hz 的 Nyquist 频率是 125 Hz。
- 能从真实数据生成可复现的波形图和 PSD 图。
- 能解释为什么原始 0.5–100 Hz/50 Hz notch 的采集设置不等于我们无需记录后续数字滤波设置。

## Phase 2：传统二分类 Baseline

**Research Question**：在同一受试者内，经典空域方法能否稳定区分左手与右手运动想象？

固定主线：

```text
EEG → 固定预处理 → epoch → CSP → LDA / linear SVM → evaluation
```

任务：

- 只使用 `left_hand` 与 `right_hand`。
- 先做 within-session，再做 cross-session。
- 使用 scikit-learn Pipeline，确保 CSP、标准化和分类器只在训练折拟合。
- 主指标优先使用 balanced accuracy；同时报告 accuracy、F1、Cohen's kappa、confusion matrix。

验收门槛：

- 固定 seed 和划分可重复运行。
- 每个 subject/session 都有结果，不只汇报总体均值。
- CSP 数学学习覆盖协方差矩阵、空间滤波、广义特征值问题和 log-variance 特征。
- LDA 与 SVM 比较使用完全相同的数据划分。

## Phase 3：空频特征研究

**Research Question**：哪些频带、空间成分和组合方式在不同受试者上更稳定？

任务：

- 比较预先定义的 Mu、Beta 和宽频带，不从测试集挑频带。
- 比较 CSP component 数量。
- Filter Bank CSP / PSD / spatial-spectral fusion。
- 比较全 22 EEG 通道与预注册的感觉运动区通道子集。

验收门槛：

- 每个超参数只在训练数据内选择。
- 同时给出平均性能与 subject-to-subject variability。
- 区分探索性结果和预先设定的验证性结果。

## Phase 4：跨被试泛化

**Research Question**：模型在完全未见受试者上损失多少性能，主要差异来自哪里？

核心设计：Leave-One-Subject-Out（LOSO）。每轮 8 名 subject 训练、1 名 subject 最终测试，共 9 轮。

防泄漏规则：

- 测试 subject 的信号不得参与标准化参数、CSP、特征选择、频带选择或超参数调优。
- 如需调参，在 8 名训练 subject 内再做 GroupKFold / 内层 LOSO。
- 所有样本始终保留 `subject`、`session`、`run`、`trial` 元数据。
- 同一 subject 的 trial 不得被随机拆到训练和测试两侧来冒充 cross-subject。

输出：

- 每个 held-out subject 的指标和混淆矩阵。
- mean、standard deviation、median、范围和置信区间（方法确定后再冻结计算方式）。
- 与 within-subject、cross-session 的同口径比较。

## Phase 5：深度学习 Baseline

在传统方法可靠后才开始。

- EEGNet 为第一深度学习 baseline。
- 必要时加入 DeepConvNet。
- 与 CSP+LDA、CSP+SVM 使用同一数据版本、epoch、划分和指标。
- 报告随机种子重复、训练曲线、早停规则、参数量和计算成本。
- 不因模型更复杂而默认其更科学或更准确。

## Phase 6：进一步科研

只有在 LOSO baseline 稳定后，才依次评估：

1. 简单 subject adaptation。
2. 统计量或协方差对齐。
3. Transfer Learning / Domain Adaptation。
4. Cross-dataset Generalization。
5. Self-supervised Learning（后期候选）。

每项改进必须回答：它利用了目标 subject 的什么信息？该信息在真实使用场景是否可获得？是否与 baseline 公平比较？

## 交付物里程碑

- M1：真实数据读取、事件核对、波形/PSD/epoch 图。
- M2：可复现 CSP+LDA/SVM 二分类 baseline。
- M3：空频消融实验表。
- M4：严格 LOSO 跨被试基准。
- M5：EEGNet 公平对比。
- M6：泛化改进、统计分析、完整报告和 GitHub 清理。
