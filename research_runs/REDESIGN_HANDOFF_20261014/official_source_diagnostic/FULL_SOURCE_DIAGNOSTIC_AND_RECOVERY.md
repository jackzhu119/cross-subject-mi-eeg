# 六试次证据已核验；全量源输入诊断与恢复门

收到的12:00包此前未处理，按Library ID及SHA去重后独立核验。libfile_32129f30c0a481919797964f282fbfdd，9242字节，SHA256 7701300ad4e9491898ae03e06a783d2597f43303165155f1b4e86ecc65a7c206。13项清单全部通过，脚本/设计文件分别匹配18c51bbe…及e6aaad1b…交付，6份逐试次JSON与合并报告一致，实际退出0。

三条原异常在固定SkylakeX zi诊断分支各改变1个float32元素，完整试次hash均匹配冻结值；三条前置对照无元素改变且仍匹配。原生分支仍有原异常，不是修复完成。该结果支持zi差异足以解释这六条的最终输出差异；不能外推2592条，更不能补写冻结生成时实际BLAS身份。原结果保存在fixed_zi_result_20261014T1200Z，旧失败保留。

## 单次全量诊断设计

新脚本diagnose_full_source_fixed_zi.py，依赖上轮不可变的probe_fixed_zi_mediation.py及fixed_zi_mediation_design.json；还绑定11:19原生全量报告及12:00六试次报告的完整SHA。

1. 同c802 checkout、原runtime。先按原load_source19读取并核验18个原文件，重建2592条原生三频带数组；整体hash必须等于11:19实际值、身份hash必须等于冻结、逐试次异常必须仍为原mu三条。漂移即停。
2. 独立诊断遍历全部2592条，逐文件再次核验原SHA，严格对齐原loader样本顺序。每条mu先以原生zi校准：独立filter必须逐位等于原SciPy filter，最终float32必须等于刚生成的原生loader数组。
3. 同一试次只执行已固定的SkylakeX zi反事实分支，不搜索、不换核、不调参。先前6试次还必须保持全部反事实阶段hash一致。
4. 输出所有2592条native/fixed-zi/reference mu hash和改变元素数；比较固定zi mu整体hash与冻结，并与未改变的原生broad/beta形成“诊断组合”的三整体hash。broad/beta原生逐条和整体也严格比较冻结。
5. 只输出报告/CSV/hash/源元数据，不保存任何EEG数组、模型或目标预测。原生三频带和独立mu仅在进程内存存在，不替换loader或注册输入。

预期通过要求：18文件、108run、2592唯一ID及36人次/手别计数均由原loader审计；labels/metadata/IDs全等；原生broad/beta逐条全等；独立mu逐条2592/2592且整体hash全等；6试次阶段锚全等。任何失败都不能被“多数通过”覆盖。

## 父对话只执行一次

将本提交新脚本放入现有bootstrap并核验交付SHA。原helper/design不重新生成，不重新下载数据。输出目录必须全新：

```bash
/workspace/paper1-diagnostic-runtime/bin/python \
  /workspace/paper1-official-source-bootstrap/diagnose_full_source_fixed_zi.py \
  --checkout /workspace/paper1-source-diagnostic-c802 \
  --data-dir /workspace/paper1-readonly-probe/data \
  --helper /workspace/paper1-official-source-bootstrap/probe_fixed_zi_mediation.py \
  --design /workspace/paper1-official-source-bootstrap/fixed_zi_mediation_design.json \
  --six-report /workspace/paper1-readonly-probe/fixed-zi-mediation-run01/report.json \
  --original-report /workspace/paper1-readonly-probe/new-host-source-report.json \
  --output-dir /workspace/paper1-readonly-probe/full-source-fixed-zi-diagnostic-run01
```

唯一worker，300秒硬上限，无重试，无GPU/网络调用。使用现有约780MB MAT，不复制第二套；主数组内存约252MB，另有读取MAT和滤波缓冲，现有62GB足够；保持既有6GiB磁盘余量。小型诊断输出，通常MB级。输出已存在、既有CPU/OpenBLAS override、固定文件或证据SHA改变、任一校准漂移立即停止。

全量匹配时状态为FULL_DIAGNOSTIC_MATCH_TRAINING_STILL_BLOCKED，实际退出0；全量不匹配写出报告并退出2。异常/超时可能只有native_audit、部分CSV及日志；保留全部文件，不补造完整报告、不换目录重试。完成也停止，父对话回传整个目录、新脚本及外层退出码，附大小SHA清单并独立离机回读。

## 正式恢复条件（本次不实施）

全量诊断匹配是解释输入差异的证据，**不是当前原生流水线通过**。正式恢复至少须逐项具备：

1. 本轮完整证据独立回读通过；全量报告满足上述所有精确检查。保留所有原生不匹配、零fit失败、预算和冻结记录，不能把反事实报告替换为原生成功。
2. 明确一个可审计、版本固定的正式数值执行方案，使实际训练所调用的输入路径产生原冻结字节；不能从诊断输出挑选/修补数组，不能将独立helper偷偷替换原loader，也不能仅在源侧应用未登记的特殊规则。当前未交付这种正式方案；其代码/运行环境和对目标预处理的一致影响需要独立审查验证。
3. 正式方案必须在实际训练runtime对全部源数据再次通过原有完整hash门；验证对象是训练实际消费的输入，不能仅接受影子诊断组合。任何数值实现变化须有显式版本、对照与有效输入契约，不改冻结参考或容差。
4. 继续通过既定划分、来源审计、目标适配资格、GPU/runtime、任务注册和预算门；不复用/重置旧失败注册，不自动重新启动完成实验，不用目标测试集选择数值方案。父对话统一调度论文1/2，维持结果离机备份与关机核验。

上述正式方案未明确且原生hash仍失败之前，训练门保持关闭。历史生成时实际BLAS内核仍未知，本轮即使全匹配也不能把它写成已证事实。

## 软件验证边界

复用helper的6个合成校准/输入不变情形及3个保护检查通过；新全量脚本6个执行前保护情形（既有输出、numeric override、四份证据各自变化）通过，编译/差异检查通过。Codex未持有/下载EEG，未执行2592条全量分支，因此实际全量结果待Pod运行，不能宣称已经通过。
