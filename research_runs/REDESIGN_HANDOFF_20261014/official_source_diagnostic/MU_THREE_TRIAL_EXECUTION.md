# 三条mu异常的有界诊断交接

完整私有包350649字节SHA256 c6e7d705e16dcbde3a004a3beccbdb87ee02c8ca5b3ffdff3668bb90675ab17c已独立回读。27项清单/大小/SHA全部通过，8份代码科学文件与c802一致。18条成功传输记录与冻结原始清单一致，18条实际原址→同名lampx一跳均存在；本Codex没有下载原始EEG。原报告SHA256 a481ee98d6a1184dd6a696754b8c47a9a3bcfc6b92941393a90e7dcecbbd0a2b确认mu只有s02_1test_r2_t36、s03_1test_r0_t06、s07_0train_r0_t06三条不匹配；broad/beta、labels/metadata/IDs匹配，SOS逐值一致。原报告、实际退出码2、v2传输/监督记录按原字节追加到v2_result_20261014T111526Z；旧证据不改。

## 执行一次

获取本交付固定提交的probe_mu_three_trials.py到bootstrap目录并核对交付SHA；不更新c802 checkout，不安装包。父对话在确认无其他研究进程时执行：

```bash
/workspace/paper1-diagnostic-runtime/bin/python \
  /workspace/paper1-official-source-bootstrap/probe_mu_three_trials.py \
  --checkout /workspace/paper1-source-diagnostic-c802 \
  --data-dir /workspace/paper1-readonly-probe/data \
  --prior-report /workspace/paper1-readonly-probe/new-host-source-report.json \
  --output-dir /workspace/paper1-readonly-probe/mu-three-trial-diagnostic-run01
```

脚本读取现有A02E/A03E/A07T三文件，逐次完整SHA核验；不下载、复制MAT或训练。只处理3个异常及每条同run最近的前置二分类试次，共6个试次。原生组必须复现已有报告的异常/对照状态，否则停止，不继续解释干预。

三子进程顺序运行：native、仅NPY_DISABLE_CPU_FEATURES=FMA3、NPY_DISABLE_CPU_FEATURES=AVX2,FMA3；设置只作用于新诊断子进程，现有环境/科学代码不变。每组180秒上限，失败/超时停止，保留输出和日志。最多9分钟，正常应远短于此。输出目录须不存在；不覆盖、不自动重试、不更换目录规避失败。存在原CPU override时拒绝，需先核查。

每组先验证冻结六文件及精确NumPy/SciPy/pandas，保存构建配置、实际CPU特性、限定数值环境变量。三条异常各有一条预先规则选择的对照；broad/beta同时记录作为频带对照。记录context、CAR19、SOS、zi、filter、resample、float64 crop、float32输出的哈希。手工阶段追踪必须逐位等于原loader输出，另一次原loader调用检验本组重复性；npy内存往返验证序列化保持字节。不导出原始或处理后EEG值。

另对每条mu不匹配输出，按float64裁剪值到float32舍入中点的ULP相对距离取最近32个元素，各测试一个向上/向下相邻float32值，共最多64个独立临时副本。若某副本**完整SHA**等于冻结参考，可以辨认一个元素一相邻float32步的输出差异；这只是哈希支持的差异形态定位，不能证明历史根因或数据质量无影响。副本只在内存用于对照，永不写回、返回到loader或成为新冻结输入。未找到匹配完全不排除其他数值差异；不扩展搜索、调容差或自动改写。

comparison.json给出各CPU干预相对native的第一个改变的mu阶段与是否匹配历史参考。禁用的是NumPy派发，不代表完全禁用SciPy/BLAS中的对应机器指令；即便干预有效也只能支持该环境对该路径的因果影响，不能直接证明旧主机同因。若无差异，不能排除其他构建/库路径。所有输出仍标记TRAINING_BLOCKED。

## 验证与回传

本Codex运行5项无真实EEG验证：C/F布局合成trace与原loader一致；正负float32边界精确候选匹配且输入不变；无候选匹配正确保留不确定；已匹配不搜索；已有输出目录拒绝且不启动worker。直接运行测试函数通过（runtime无pytest，未安装）。真实3文件/6试次和服务器CPU干预尚未执行，不宣称通过。

请回传整个新目录：3组JSON、日志、监督退出码、comparison.json及completion.json（如已生成），并附脚本、大小SHA清单及外层实际退出码。退出0仅表示诊断完成，不是源输入合格或训练授权。失败保留现场，先独立离机回读。若结果仍不能定位，下一步依据实际阶段差异另议；不重跑全源库、不修改hash/容差或冻结数组。
