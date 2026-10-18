# 已批准的明确标签资格修订（v3，2026-10-18）

用户于2026-10-18 01:53:31 UTC批准：保留全部51名Yang参与者，仅纳入原始明确1/2
标签的事件；未知和缺失证据保留、不猜类别、不补时间，不改变窗口、分组或随机种子。
本目录为独立修订，原科学代码、旧run/cache、上传器及凭据均不修改。

## 冻结与科学范围

资格清单`eligibility_manifest.json` SHA256：
`5291d362185a8db9bf45ddc95d9cb49d40de57893d2fd4da8681a802b5ab36f9`。
它绑定完整153session的原始事件路径/大小/内容SHA与真实计数，并保留五个异常session
完整事件序列。正常session不能自动放宽，任何未知文件、计数或审阅过的事件序列变化均失败。
原时钟清单及完整原始文件SHA校验继续生效。

- 五个标签不足session：023/01=99+100、024/02=99+100、024/03=99+96、026/01=99+100、032/02=99+100。
- 255共有5个，四个出现在上述缺标session；另一个位于017/02的105.625秒，
  该session仍有100+100明确标签。255不等于缺失试次，也不等于类别1。
- Yang明确标签合计30591：1=15295、2=15296。S9=2592、S29=14590、S60=33183。
- 参与者、折、种子、神经模型/传统模型、每轨迹5120更新、108轨迹、选轮规则、
  marker+[2,4)窗与[0,6)上下文、外部评估及主要比较不变。
- 资格变化在config/study.json中明确登记；不把变更后的run冒充旧冻结执行身份。

分段使用原始9号标记的实际位置，绝不按保留事件每40个重分。
每个保留事件保存原始事件索引、原始观察事件序号和段号，保留原始onset及顺序。
现有trial_ordinal仅表示保留顺序，不能解释为恢复出的原计划试次号。
9号标记作为**操作性原始分隔位置**审计，尚无独立官方语义说明，不用于补标签或推定缺失onset。
未知事件含时间/原始索引完整保留；缺失只记相对原计划计数的缺口，不构造不存在的事件。

## 31份缓存的可验证复用

仅允许来源模块SHA为
`a930de67cbc15d1db4c5d7d2b8ee05a436ebc20e564e72800c1913aaeee86b44`
的BNCI01–09及Yang01–22。生成器以AST检查确认数值预处理、解码、BNCI/Dreyer处理、
窗口计算等函数未变；再验证NPZ独立回执SHA、数组/标签/元数据哈希、原始文件全SHA，
Yang缓存逐事件核对原始标签、sample、anchor及原始分段。017的额外255也追加明确审计。

新缓存是独立字节副本，保留原NPZ和嵌入audit身份，不伪称数组重新生成；新兼容性回执
单独记录旧/新模块SHA及逐事件证据，运行时纳入source_inputs provenance。
旧文件不被覆盖；新目标已有不同内容则失败。复用不满足任一校验时停止，不伪改execution_identity。

## 唯一现场操作者执行顺序

从本提交的干净公开检出运行；`PUBLIC_CHECKOUT`不是用户原code目录。
现有锁定venv不变，无需重新安装或再次执行完整bootstrap。

```bash
python3 "$PUBLIC_CHECKOUT/research_runs/YANG_LABEL_ELIGIBILITY_20261018/build_eligibility_copy.py" \
  "$PUBLIC_CHECKOUT/research_runs/SOURCE_EXPANSION_20261017" \
  /workspace/paper1_expansion/code_eligible_v3_20261018

/workspace/paper1_expansion/venv/bin/python \
  "$PUBLIC_CHECKOUT/research_runs/YANG_LABEL_ELIGIBILITY_20261018/reuse_verified_caches.py" \
  --code /workspace/paper1_expansion/code_eligible_v3_20261018 --root /workspace/paper1_expansion

/workspace/paper1_expansion/venv/bin/python \
  "$PUBLIC_CHECKOUT/research_runs/YANG_LABEL_ELIGIBILITY_20261018/verify_eligible_people.py" \
  --code /workspace/paper1_expansion/code_eligible_v3_20261018 --root /workspace/paper1_expansion
```

依次须看到`PASS_31_COMPATIBLE_CACHES`和`PASS_REAL_FOUR_AFFECTED_PEOPLE`。
第二步重新完整核验原始文件与缓存，但不重复信号预处理；第三步实际预处理023/024/026/032，
应分别599、594、599、599试次，并写入新缓存，之后正式runner直接复用这四人。
任何失败都保留旧缓存/原始文件并停止。新代码目录若已存在，生成器拒绝覆盖；
应先核对已生成manifest，不能为重试删除原始代码或旧run。

现场确认旧worker已退出、无并行训练，验收通过后执行：

```bash
bash "$PUBLIC_CHECKOUT/research_runs/YANG_LABEL_ELIGIBILITY_20261018/START_APPROVED_RUN.sh"
```

脚本重新验证代码manifest、两份验收回执与35份缓存SHA，持原launch.lock派发新run。
新运行：`runs/expansion18_eligible_v3_20261018`；新缓存：`data/processed18_eligible_v3_20261018`；
新日志：`run_eligible_v3_20261018.log`。启动回执不等于实际GPU拟合，须查看status/日志/检查点。
未完成源预处理前不会做GPU拟合；用户授权的原全训练计划随后照常执行。

旧归档器观察旧run。本修订不读取或修改它及任何上传秘密配置；
新run完成不能冒充已获自动备份，最终结果回传需后续单独衔接。

## 本地验证与边界

测试命令：`python3 -m unittest discover -v -s research_runs/YANG_LABEL_ELIGIBILITY_20261018 -p test_eligibility.py`。
覆盖真实五异常事件、017额外255、原始分段/不重排、不推断标签/时间、固定清单和总数、
改动身份/计数/onset拒绝、缓存来源范围、生成副本仅批准配置变化与模型/数值合同保持。
还在生成副本运行合成数据路径检查。具体回执随validation提供。
本地测试不是现场31缓存复用、异常人真实预处理、GPU开训或真实备份完成。
