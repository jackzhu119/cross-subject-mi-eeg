# 三模式诊断之后：OpenBLAS滤波初始状态定位

## 已独立收到的事实

私有Library libfile_ea934578c2748191b02644ece7ae0d38包22846字节，SHA256 7a947c28e03134f3afe3b7dcd8a14ba4e8a39977ba0dbd519735f3db756e0fc3；14清单文件大小SHA全部通过，路径安全且无重复。实际脚本等于已交付7fb083e7…版本，三worker退出0。独立比较六试次全部阶段hash，native/no_fma3/no_avx2_fma3完全一致；重复计算及npy内存往返均一致。原始结果与核验记录追加在mu_result_20261014T1130Z，未改旧证据。

舍入候选的已完成结果：s03_1test_r0_t06的channel_index=5/time_index=164向上一个相邻float32值；s07_0train_r0_t06的channel_index=18/time_index=278向上一个相邻值，各自临时副本完整SHA等于冻结参考。s02_1test_r2_t36在预设64个单元素候选中没有匹配。两条的差异形态有完整哈希支持，第三条仍未知。候选搜索到此停止，不再扩展或将任何候选变成训练输入。

## 冻结环境的证据边界

- 源指纹receipt生成于2026-10-13 08:48:07，保留NumPy2.3.5、SciPy1.17.0、loader/config/CSV SHA和SOS值，未保留当时OpenBLAS实际内核、wheel/共享库SHA或zi。
- 同日前07:15的core_source_input_probe.json已经给出相同三个整体数组SHA；07:42 core_cpu_software_runtime.json记录Python3.12.14，但它的scope明确是CPU软件测试，不可冒充08:48指纹生成进程的完整环境证明。
- eae基线中SOURCE_INPUT_DIAGNOSTIC_VALIDATION.json记录2026-10-14 07:31本地2592试次全部匹配，CPU包含AVX512。它不能证明这次11:30服务器环境相同，也未记录OpenBLAS实际内核。
- 服务器当前报告Python3.12.3，NumPy/SciPy对应OpenBLAS0.3.30 DYNAMIC_ARCH构建。show_config中“Haswell”是构建配置文本，不能直接当作运行时corename。本次新探针专门读取实际corename。

## 新发现：无EEG的受控局部复现

本Codex对当前同一NumPy/SciPy安装运行两个新子进程，只改变OPENBLAS_CORETYPE=Haswell；不是重跑EEG/训练。实际默认corename=SkylakeX，对照=Haswell；NumPy OpenBLAS二进制、_umath_linalg和SciPy _signaltools源码SHA两组完全相同。

SciPy1.17.0现有源码路径：sosfiltfilt → sosfilt_zi → lfilter_zi → xp.linalg.solve。lfilter_zi对每个SOS段解2×2方程；NumPy路径通过其OpenBLAS/LAPACK执行。探针独立构造同一矩阵/右端，要求solve结果字节与原SciPy lfilter_zi相同。

控制结果：三个频带SOS及所有段方程矩阵/右端完全一致；mu第3段（零基index2）解发生字节差异，合成zi也改变。broad第4段独立解发生差异，但最终合成zi没有改变；beta不变。因此不能泛称“只有mu的任何中间计算有差异”。

mu zi SHA：

- 当前Codex默认SkylakeX：6a197eaf27bf51055aadb102c0f42811e759cbbe1c089d1cd59684e0b8ae08a3
- 同安装Haswell对照：ff50d1508f773d568e54fbb66539221d5a08881fc985e44024134a6cb13f47d8
- 服务器已回传三模式mu zi：ff50d1508f773d568e54fbb66539221d5a08881fc985e44024134a6cb13f47d8

这是**OpenBLAS内核选择能导致mu zi字节差异**的实际局部因果证据，解释了为何仅禁NumPy派发不能排除此路径。不是全部3条历史最终数组差异的完整根因证明，也没有将任何zi或输出注入原loader。完整本地控制结果在openblas_coefficient_local01。

## 下一步仅一次系数探针：不读取EEG

固定交付probe_openblas_filter_state.py到现有bootstrap目录，核对交付SHA。保留c802 checkout及runtime，父对话执行：

```bash
/workspace/paper1-diagnostic-runtime/bin/python \
  /workspace/paper1-official-source-bootstrap/probe_openblas_filter_state.py \
  --checkout /workspace/paper1-source-diagnostic-c802 \
  --output-dir /workspace/paper1-readonly-probe/openblas-filter-state-run01
```

仅两个顺序子进程：native和Haswell，每组30秒；读取固定配置、六文件Git身份、数值库，计算公开滤波系数及2×2方程，完全不读MAT/目标/GPU/网络。不安装、不复制数据、不训练、不改冻结值、不重复候选搜索。控制先确认native支持AVX2/FMA3；不强制SkylakeX或AVX512到服务器。读取NumPy库的实际corename/config，必须确认Haswell对照生效；保存二进制/源码SHA及方程/解的精确hex。它们是公开滤波系数，不是EEG幅值。

## 停止条件与解释

1. 已有输出目录、现有CPU/OpenBLAS override、冻结文件/版本不符、库符号不符、硬件不支持、显式方程不等于SciPy结果：立即停止，不换目录或安装包绕过。
2. 子进程失败/超时：保留日志和监督文件，不重试。两组完成后也停止；最多60秒计算，不继续内核枚举。
3. 若服务器native已是Haswell且对照不变，这是同路径一致性对照，不能包装成第二个独立变化实验。若报告中的zi不等于11:30原生记录，先查执行环境漂移。
4. 回传整个新目录、脚本和外层退出码，附大小SHA并离机回读。无需重复2592试次或此前六试次。
5. 本步只能进一步确认服务器实际库/内核与系数路径。无论结果如何，保持训练阻塞。若要建立zi到三条最终差异的完整因果链，须另行设计不改正式输入的有限阶段对照；本脚本不执行该步骤、不修补数组。

验证：当前Codex两个真实系数子进程成功；方程与原SciPy逐位一致；已存在目录拒绝且所有原字节不变；既有override拒绝且不创建输出。未在Pod执行本脚本。历史生成时准确BLAS身份和中间数组仍缺证，不能从当前本地实验补写旧环境。
