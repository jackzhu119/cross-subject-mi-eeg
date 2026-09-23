# 正式论文提纲

状态：2026-09-23，证据积累阶段。依用户最新要求，先做实验与文献核查；此前 `docs/*manuscript*` 两份样例是探索性工作稿，不作为最终投稿文稿。

1. **Abstract**：最后写。数据集、最终任务、主比较、主要效应和限制确定后再定稿。
2. **Introduction**：定义 source-only cross-subject MI；明确目标域信息预算；已有 CSP+PSD 和多频带方法，潜在贡献须由严格控制的泛化、稳健性、机制实验和外部数据集支持。
3. **Related Work**：CSP/FBCSP；EEGNet/空间频谱深度模型；domain generalization 与 adaptation；artifact/数据划分方法学。按协议而非最高分组织。
4. **Materials and Methods**：数据许可与来源、事件时间锚点、四分类、固定预处理、source-only 拟合、LOSO 与内层按被试验证、种子和可复现记录。
5. **Experiments**：传统基线；后续 EEGNet；空间、频谱及融合消融；容量/计算成本控制；伪迹与时间窗敏感性；必要时外部数据集。
6. **Results**：仅链接真实运行。P2–P4 二分类结果列为 pilot；Q4-E001 四分类九人 LOSO 已完成并独立验证，真实结果见 `docs/q4_e001_results.md`。多频带平均未超过宽频 LDA；后验设计的维数消融 Q4-A001 见 `docs/q4_a001_capacity_results.md`，不可当作外层独立参数选择。
7. **Discussion**：逐被试异质性、方法差异、负结果、影响数据分布的处理步骤；不把相关性改善当分类改善。
8. **Limitations**：单数据集九人、已看过的 benchmark、LOSO 重叠训练依赖、离线零相位、专家伪迹标记、资源公平性。
9. **Conclusion**：仅陈述最终得到支持的命题，不预先写“显著提高”。

## 当前结果入口

- P2：`outputs/P2-E001/summary.csv`，三种部署情境的传统二分类基线。
- P3：`outputs/P3-E001/subject_metrics.csv`，固定空间/频谱消融与同测试 ID 的训练伪迹政策。
- P4：`outputs/P4-E001B/subject_metrics.csv`，源拟合 EOG 回归的探索性负结果。
- 统计补充：`docs/statistical_interpretation_addendum.md`。
- 文献矩阵：`references/literature_matrix.md`。Q4 四分类结果说明：`docs/q4_e001_results.md`；后验维数消融：`docs/q4_a001_capacity_results.md`；下一阶段 EEGNet 协议草案：`docs/q5_eegnet_protocol_draft.md`。原始运行与验证分别位于 `outputs/Q4-E001/`、`outputs/Q4-A001/`。
