# 已核验11:45系数结果；下一步为一次固定初始状态诊断对照

本次消息此前未处理。私有包libfile_aeb4457935f481918af111f863b1978c（8510字节，SHA256 461f7d08a0d4c4a2a3c72bc6944f4f1c530746eb23df2aa92145cfe4d8ae27da）独立回读，10项清单大小/SHA全部通过；原脚本SHA对应a226b01a…交付。native及Haswell对照均退出0，实际corename均Haswell，所有SOS/zi/方程矩阵/右端/解相同；mu zi与11:30六试次一致。相关原始结果及核验记录追加在openblas_server_20261014T1145Z。

服务器NumPy OpenBLAS共享库、_umath_linalg扩展、SciPy _signaltools源码三个SHA，与当前Codex SkylakeX/Haswell实验也全部一致。由此排除了这三个被核验文件的字节差异；没有宣称所有依赖都相同。服务器同内核对照是稳定性证据，不是新的干预效果。

## 当前因果链及缺口

同一Codex安装仅切换OpenBLAS内核，产生mu第3段solve及合成zi差异；Haswell zi精确匹配服务器。服务器已确认Haswell。因此已定位一个与两主机差异一致的数值执行机制。仍缺“仅这一zi差异是否足以解释指定三条最终输出差异”的实测中介环节。

冻结生成环境证据没有新增：08:48指纹receipt未记录当时实际BLAS内核/二进制/zi；07:42软件环境不是生成进程证明；eae中07:31的完整本地重建匹配并含AVX512，但未留实际corename。当前SkylakeX结果不能补写为历史冻结生成时事实。原始阶段数组缺失，不能宣布完整历史根因已证明。

## 固定设计，禁止搜索或修补

脚本probe_fixed_zi_mediation.py和设计文件fixed_zi_mediation_design.json共同固定。设计只含既有实测Haswell与SkylakeX公共滤波初始状态的精确hex、SHA，以及11:30原生结果SHA；不是按试次输出寻找参数。科学loader、冻结输入、参考hash、容差、划分均不改。

只在独立诊断计算中比较两条分支：

1. 当前Haswell zi校准分支：公开SciPy1.17 pad27前向/反向滤波方程必须逐位等于原sosfiltfilt；context、CAR及mu filter/resample/crop/float32全部阶段必须与11:30原生结果一致。
2. 固定zi反事实分支：同一context、SOS、滤波/重采样/裁剪运算，仅在这个独立函数的显式参数中使用已观察的SkylakeX zi。无猴子补丁、无loader替换、无新内核、无枚举/舍入候选。它是用于判断初始状态影响的诊断分支，绝不作为科学输入。

每个分支仅在内存产生暂时输出，写出的只有阶段SHA、匹配布尔值和与原生分支不同的元素数；**不写出或替换任何EEG/科学数组，不把反事实输出送入训练，也不把它登记为新冻结输入**。该计算不借助目标数据或模型结果。

对象仍严格为3个异常和3个既定前置对照，仅读现有A02E/A03E/A07T，完整原文件SHA每个检查一次。仅处理mu；broad/beta不重复计算。读取本地原生阶段结果和已固定的CSV SHA，拒绝环境或输入漂移。

## 父对话执行一次

下载本提交的两个文件到bootstrap目录并分别核对交付SHA。保留原checkout、runtime、所有旧结果；不要安装包或更改环境变量：

```bash
/workspace/paper1-diagnostic-runtime/bin/python \
  /workspace/paper1-official-source-bootstrap/probe_fixed_zi_mediation.py \
  --checkout /workspace/paper1-source-diagnostic-c802 \
  --data-dir /workspace/paper1-readonly-probe/data \
  --prior-native /workspace/paper1-readonly-probe/mu-three-trial-diagnostic-run01/native.json \
  --design /workspace/paper1-official-source-bootstrap/fixed_zi_mediation_design.json \
  --output-dir /workspace/paper1-readonly-probe/fixed-zi-mediation-run01
```

唯一worker限180秒，无重试；输出目录必须不存在。实际科学文件Git字节、依赖、design SHA、prior native SHA、三个原文件SHA、原生zi或任一校准阶段不匹配立即停止。既有CPU/OpenBLAS override拒绝。异常保留逐试次JSON、日志和监督退出码；不删除重跑。

## 结果解释与硬停止

- 若反事实分支使3条异常全部精确匹配冻结mu，且3条对照仍匹配：支持“已观察的zi差异足以解释这6条的最终哈希差异”。这仍不是全2592条验收，更不是历史生成机器身份的证明，不放行训练。
- 若只部分匹配、控制试次受影响或无匹配：保留反证，说明单一zi不足以解释全部现象；不改zi、不换内核、不扩大候选。
- 校准失败或超时：本轮结论不可用，保留失败。完成无论结果好坏也停止，只回传整个新目录、两个固定文件、外层退出码及大小SHA清单；独立离机回读后再决定后续。不得自动追加全量重建或训练。

本Codex验证6个无EEG合成校准情形（3频带×C/F布局）与原SciPy输出逐位一致且输入/zi不变，3个执行前保护（输出已存在、既有override、design修改）通过；未执行服务器真实6试次。这里不会再重复前两轮已完成实验。
