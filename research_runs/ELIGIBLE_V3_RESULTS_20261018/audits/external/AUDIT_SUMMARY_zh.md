# 论文1外部预测与统计只读复核

日期：2026-10-18。协议：paper1_source_expansion_18ch_dimensionless_eligible_v3_20261018。

## 结论

**已保存预测的身份完整性及统计算术复核通过：1,179 项检查，0 项失败。**

本审计直接读取导出的神经网络 logits 和 CSP 概率，独立重算指标及推断统计。没有导入实验模块执行、反序列化模型/pickle、重训、重新 forward、访问 Pod、修改冻结代码/配置或依据目标结果改变方案。它是 saved predictions 算术复核，不是原始 EEG 重新处理或检查点重放复现。

## 可直接用于探索性结果部分的数字

冻结主比较：S60−S9，BROAD，tail_min_recall，终点为逐人较弱类召回率。

- S9：27.3137%；S60：48.4804%。配对均值差 **+21.1667 个百分点**。
- 配对 t：t(84)=10.4084，双侧 p=8.8841×10⁻¹⁷；95% CI **[17.1226, 25.2107] 个百分点**。
- 配对参与者 percentile bootstrap：10,000 次，种子 20261016；95% CI **[17.1468, 24.9512] 个百分点**。
- 85 人中，72 人提高、10 人下降、3 人持平；配对差中位数 +21.6667 个百分点。此为描述性人数，不是新增预设检验。

三项包内预设次要比较的 Holm 家族保持完整：

| 比较 | 差值（百分点） | 未校正双侧 p | Holm p |
|---|---:|---:|---:|
| S60 tail_min_recall−mean_ba，较弱类召回 | −0.8725 | 0.509760 | 0.999859 |
| S60−S29，BROAD/tail_min_recall，较弱类召回 | −0.5490 | 0.499929 | 0.999859 |
| S60−S9，BROAD/tail_min_recall，BA | +5.8529 | 1.7805×10⁻⁹ | 5.3414×10⁻⁹ |

以下为三种规模的描述性 BA，均为逐种子计算后先平均到参与者、再跨85人平均：

| 方法/选轮 | S9 | S29 | S60 |
|---|---:|---:|---:|
| BROAD / tail_min_recall | 58.3186% | 64.1078% | 64.1716% |
| MU_BETA_SHARED / tail_min_recall | 60.1520% | 63.6667% | 63.8775% |
| CSP+shrinkage LDA / fixed | 60.1324% | 64.0196% | 65.3775% |

CSP为单独描述性基线，没有新增其与神经网络的假设检验。全部48个神经条件及3个CSP条件的均值、SD、SE、t CI和bootstrap CI均重算核对。fixed20及其他选择器结果已保留在重算CSV，不据目标得分另选“主方法”。

## 身份、完整性与统计单位

- 神经表 979,200 行，48 个条件×3 种子×85 人×80 试次；12,240 条逐人逐种子指标、4,080 条跨种子逐人指标。
- CSP表另有 61,200 行，3 个条件×3 种子×85 人×80 试次；765 条逐人逐种子指标、255 条跨种子逐人指标。两者总计 1,040,400 行，不能把 979,200 写成含CSP的总数。
- 人员为 provider 1–87，排除17与41。每人两个 acquisition runs，各40试次、左右各20；每人合计左右各40。所有条件/种子内部无重复、无缺失、无非有限预测、无额外人员、无未知标签，两个类别均存在。没有恰好平分的 logits/0.5 概率。
- 神经与CSP的6,800个唯一 participant/trial ID及标签完全一致。每人的规范trial ID、每个run的类别计数、标签数组SHA256与 external_inputs.json 的输入审计逐一相符。170个原始EDF的路径、字节数和哈希声明与包内Dreyer下载清单一致。
- 神经表的epoch字段与已冻结选择器逐一一致。同一 level/pipeline/seed/epoch 的别名预测逐值相同。144组condition×seed输出对应99个不同的选中检查点；去掉epoch别名重复为673,200行。这些检查点仍来自18条最终训练轨迹，不能当作99或144次独立重复。
- BA=(left recall+right recall)/2；较弱类召回先在每个种子内取min，再平均3种子。不是先平均logits的ensemble，也不是先平均两类召回后再取min。
- 统计单位确为85名外部参与者，配对t自由度84。种子、CV fold、试次均未扩张样本量。bootstrap按参与者整组配对重抽样。
- 重算与保存表的最大指标差约3.55×10⁻¹⁵，BA/较弱类召回和各CI差约2.22×10⁻¹⁶，符合浮点舍入；全部配对差、t、p及Holm一致。

## 仍不可写的结论与未覆盖证据

1. Dreyer2023既往暴露不明，只能写探索性外部评估；不能写首次使用、严格独立确认或确认性验证。冻结包中的“预设”不等同于本审计证明了外部预注册。
2. 不能声称S60优于S29，或tail_min_recall优于mean_ba；相应比较均没有支持改善的证据。不能声称所有人都受益，主终点有10人下降。
3. 次要p值做了Holm三检验校正，所有报告的95% CI仍是点态、未做多重性校正的区间；不能称为同步/家族覆盖区间。
4. 这些CI反映这85名参与者间的变异，并条件于已拟合轨迹及3种子平均；没有完整覆盖训练随机性、源群体抽样、固定S29子集选择或跨数据集泛化的不确定性。
5. 扩源同时改变人数、不同试次数和采集队列/混合分布，不能归因为纯粹增加参与者人数的因果效应。BROAD与共享双频带并非独立架构。
6. 本审计确认的是保存预测与输入审计声明的一致性，未直接重读原始EDF、重新计算处理后的X/metadata哈希或核验信号级重复，未从检查点重新推理。因此不能称为独立原始数据复现或检查点重放通过。原始类别解释、目标访问时序和源选轮过程仍需对应专门审计；未因算术通过而自动证明无泄漏。
7. 沿用冻结方案的Yang时间锚与单位限制，不新增物理量/精确MI相位等同的主张，不与历史19通道实验直接作数值等价比较。

## 追溯与文件

输入总包：21,250,082 bytes，SHA256 36b47206748b364eabc8f9a6d193d9e13fa54c0a96372b912cfca8179573df5e。

原结果ZIP：21,240,637 bytes，SHA256 df8fdc4a43139acb4236ead749b74736a5bedaea6d8606c3bcc69234755fe02f。

- audit_results.json：机器可读结论、全部关键数值、运行库版本、源文件哈希及脚本哈希。
- audit_checks.json：1,179项检查及通过状态。
- audit_external.py：独立重算脚本。仅读取inputs/及指定原总包；写入本审计目录。没有调用原实验统计函数。
- neural_recomputed_subject_seed_metrics.csv、neural_recomputed_per_subject_metrics.csv：神经逐人算术结果。
- csp_recomputed_subject_seed_metrics.csv、csp_recomputed_per_subject_metrics.csv：CSP逐人算术结果。
- neural_recomputed_condition_summaries.csv、csp_recomputed_condition_summaries.csv：全部条件汇总/CI。
- neural_recomputed_comparisons.csv、neural_recomputed_paired_differences.csv：四项固定比较及逐人配对差。
- verified_external_identity_roster.csv：85人trial manifest/标签数组哈希。
- audit_execution.log：执行完成输出。

所有审计文件位于 /workspace/shared/paper1-external-audit-20261018/，原始证据包和其原解压目录未改写。
