# 当前唯一执行交接：复用已修复环境，先取得真实验收

> **Current correction:** Financial execution prerequisites below are superseded-by-user for source_raw_restore/source_cpu_acceptance. Do not wait for billing or balance. Use [the narrow amendment and exact two-stage commands](repaired_acceptance/FINANCIAL_SUPERSESSION.md) with its new fixed pin. Earlier dollar-review wording is historical; it is not a condition for these two operations. All technical/resource/Paper2 and no-fit boundaries remain.

此页合并当前步骤，避免重复安装或另起任务。**交给 dot 执行；本助手没有
Pod 执行通道，也未观察到新一轮现场验收或训练。** 代码推送不是现场运行回执。
论文2保持独立优先；不 Stop / Restart / Terminate，不更改其 cp311 环境、全局包或数值线程。

## 立即执行的下一步

1. **不再修复或安装。** 已独立核验的真实修复原包为442155 bytes、
   SHA256 `7ebd6080181ec3bb5d2c9faf74d754af68c0ea4eea48978467df713e8465f8a1`。
   该次离线修复退出0，记录97个 distributions。继续使用
   `/workspace/paper1-training-runtime-cp312-run01`，保留独立
   `runtime_repair_run01.json`；不能伪造原 preparation 成功。
   这是历史实测证据，不替代本次现场路径/文件核对。
2. **作者48小时时间授权已经收到，不再询问同一授权。** 沿用
   [固定授权及小包命令](repaired_acceptance/AUTHOR48_PIN.md)，执行代码仍固定为
   `709a213c04689f4c388ee40c7cfa24b4d4f45ab1`。不要拿最新文档提交代替这个执行版本。
   dot/父侧完成真实美元覆盖、现场余量和论文2非干扰检查，再签发各自新 slot；
   这不需要作者重复提供密钥或重复批准48小时。
3. 检查现有源恢复/验收的独占标记及完整回执。若已执行，返回原证据，**不要重跑**。
   若尚未执行且现场前提成立，执行
   [DOT_NEXT.md 的 Step A 原命令](repaired_acceptance/DOT_NEXT.md#step-a--restore-the-18-source-originals-with-a-new-source-only-slot)：
   只恢复缺少的18个官方同字节源 MAT，保留779873919-byte原始清单及全部SHA。
4. 父侧复核实际成功的 source restore 回执，签发独立新 CPU acceptance slot。
   执行 [Step B 原命令](repaired_acceptance/DOT_NEXT.md#step-b--one-actual-repaired-runtime-cpu-source-acceptance)：
   使用同一修复 cp312 环境及134436/12299-byte已审计历史原包，
   进行一次实际 training-role 导入/源输入验收。不得重跑旧全量诊断。
   原18文件/108runs/2592trial和三频带严格hash门不变。

执行版本/路径变量仍是：

```bash
export P1_ACCEPT_DIR=/workspace/paper1-acceptance-code-709a213c
export P1_ACCEPT_REVISION=709a213c04689f4c388ee40c7cfa24b4d4f45ab1
```

以上变量不是启动命令；完整下载校验、真实 review/slot 参数、超时和执行命令均在
上述固定 pin 与 Step A/B 中。不能把 `PLAN_ONLY` 模板改名当成真实审核。
如果原包未恢复，通过既有已授权 HTTPS/browser 传递原字节并校验；
不猜R2键、不重试既有401、不重建SSH或其他凭据。

## 不能把验收成功直接当成开训

验收成功应得到
`REPAIRED_ACTUAL_TRAINING_RUNTIME_SOURCE_MATCH_OTHER_GATES_PENDING`，
而不是训练完成。dot应返回以下小证据，原始EEG和轮子二进制不入GitHub：

- 本次精确命令、开始/结束UTC、退出码、真实新review/slot及其SHA；
- `source_restore_run01.json`、源恢复journal/log及完整性清单；
- `formal_source_acceptance.json`、`repaired_runtime_bound_acceptance.json`、
  本次验收log/attempt及完整性清单。

后续训练必须继续原任务 `20261014T071918Z-exploratory-89b0c07d` 的身份与账本，
保留原 `array_hashes` 失败。旧私有最新状态、费用、GPU小时和checkpoint仍不能
从历史公开0-fit快照推成0。$10总额/$2预留、fit/update计数不重置；
48小时CPU恢复可用窗口不能冒充新的48小时GPU付费额度或原训练预算通过。

已静态定位的实际训练入口阻塞必须一起处理，不能只换下载地址：

1. `prepare_data.prepare()`仍无条件走R2导入；官方源/目标cache的JSON映射
   **尚未接入生产路由**。目标174 EDF必须按固定官方路径/大小/SHA恢复，
   并通过既有header/event/native-context及三频带input hash门、85人/6800事件冻结roster。
   本轮不下载或读取目标EEG，不用GDF/BDF替代EDF。
2. 原 `cloud_supervisor.launch_locked()` 的resume仍核对旧注册版本、原hostname/GPU UUID、
   runtime lock及预算；不能用新容器冒充原机器，不能直接调用旧launcher强行恢复。
3. `train_exploratory`在实际fit前调用 `private_recovery.from_environment(job)`，
   需要真实私有HEAD与COMMITTED snapshot连续性，并在fit/update期间维持备份约束。
   官方EDF恢复只替代原始数据传输前提，**不替代私有checkpoint/备份门**。
4. 原训练预算校验仍包含累计8GPU小时及其绝对期限规则。真实旧账本/费用上界、
   checkpoint恢复和当前机器过渡必须以追加操作修订及真实审核证据绑定；
   不允许用本页、CPU授权或metadata匹配伪造PASS。

这些门实际通过后才接原训练/验证/发布链，不能另起重复fit。
不要为了等待下游代码而延误已具备前提的源恢复/实际CPU验收。

## 此次新增代码的用途

[transport_union](transport_union/README.md) 提供18+174份冻结输入和五份实际JSON回执的
严格跨绑定校验。它关闭metadata拼接缺口，拒绝伪R2回执、错任务、漏项和错误SHA；
**它不读取实际cache，不接生产路由，不发slot、不授权训练。**
81项针对性软件测试通过；没有重跑任何科学实验或现场验收。

当前助手无法调用dot聊天或Pod执行通道，因此本页是待dot执行的固定交接，
不是已发送给dot、已部署到Pod或已开始训练的声明。
