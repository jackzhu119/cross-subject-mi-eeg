# 新主机源数组不匹配：证据接收前检查

父对话报告v2 attempt 20261014T111526Z-fa8dc4669cd5于11:15:26–11:16:05 UTC退出0，18/18原始文件共779873919字节完整重算通过；c802诊断于11:18:38–11:19:12退出2，NEW_HOST_SOURCE_INPUT_MISMATCH_BLOCKED，0 fits。此处尚未独立读取该次Library证据，不能补写实际频带差异数量或宣称根因。

## 已核查的生成与比较路径

冻结生成器为REDESIGN_EXPLORATORY_20261013/scripts/build_source_duplicate_reference.py，首次证据提交543feb2f，receipt时间2026-10-13T08:48:07.806578+00:00。它调用同一load_source19，使用core_experiment_v1.json，读取旧本地bnci目录，输出2592行逐试次指纹及整体数组/labels/metadata/IDs指纹。不要执行此生成器：它直接覆盖冻结证据。

当前loader字节SHA与receipt helper_sha256一致；原配置SHA与config_sha256一致；CSV SHA与reference_sha256一致。原配置与cloud配置不同的九项仅为实验名称、状态、授权及目标资格信息，transform实际使用的固定处理字段相同。诊断器比对六个冻结文件的Git字节后，使用与生成器相同array_hash（shape、dtype.str和连续字节）；逐试次按sample_id查找，不是CSV行顺序配对。实际报告还需核查三个身份指纹和逐频带mismatch，不能只读状态行。

数值路径：scipy.io.loadmat(simplify_cells=True) → 真实19通道选取 → 原始cue=trial-1+500 → 1500点float64 context → CAR19 mean(axis=0) → butter四阶SOS → sosfiltfilt odd/padlen27 → resample_poly(16,25,kaiser5,constant0) → crop320:640 → 连续float32。整体数组shape2592×19×320，每频带单试次SHA也使用shape19×320。

冻结记录NumPy2.3.5、SciPy1.17.0；新诊断还强制pandas2.2.3。版本号不包含wheel/编译器/BLAS/CPU派发身份。检查本地安装的SciPy1.17.0源码：sosfiltfilt调用sosfilt_zi，后者调用lfilter_zi，内部为xp.linalg.solve；重采样还构造firwin(501,1/25,kaiser5)系数后乘16。因此即使SOS一致，还需区分初始化、FIR和数据处理阶段。这里列的是待证假设，不是已确定根因；不改任何数值设置。

本Codex现有精确数值runtime离线生成三组SOS，均与冻结receipt逐位一致，max_absolute_difference=0。这不代表服务器SOS也相同，需要读其报告。

## 报告到达后最小顺序

1. 独立核对离机包大小SHA及所有成员，保存退出码2和旧记录；核验报告确为本次固定代码/原始输入，不重复全量2592试次重建。
2. 先看labels/metadata/IDs。若不一致，优先查MAT解析、原始run/trial枚举和身份，不先归因浮点。若三者匹配，再看各频带整体与逐试次差异、最早sample_id以及SOS差异。
3. 可由父对话选择运行下述无EEG探针一次，保留原runtime，不安装依赖、不切线程/CPU模式。比较双方SOS、sosfilt_zi、FIR及同一整数构造合成信号的最终SHA，并比较构建配置、编译库SHA及CPU特性。其结果只定位环境差异，不证明历史数据值差异或替代原始指纹。
4. 仅当报告与探针仍不足，再准备以报告中最早不匹配sample_id为对象的单试次阶段探针：原始选通道context→CAR→过滤→重采样→float32裁剪，记录shape/dtype/strides及阶段SHA，不导出EEG值。这个真实数据阶段尚未实现或执行，不先选择试次、不重跑整库。历史冻结只存最终SHA，不能由SHA计算误差大小、ULP或证明差异无害；若缺旧阶段数值，明确证据缺口。

## 无EEG探针的父对话命令（可选下一步，尚未在服务器执行）

把本固定提交的probe_numerical_runtime.py放在bootstrap目录，先校验交付SHA。保持c802 checkout不变，输出新文件：

```bash
/workspace/paper1-diagnostic-runtime/bin/python \
  /workspace/paper1-official-source-bootstrap/probe_numerical_runtime.py \
  --checkout /workspace/paper1-source-diagnostic-c802 \
  --output /workspace/paper1-readonly-probe/numerical-runtime-probe.json
```

探针先验证六个历史文件及精确依赖，不读MAT、R2、目标、GPU或网络；不创建模型；已有输出拒绝覆盖。只读取白名单数值环境变量，不枚举凭据。约数秒，编译库哈希使用当前安装文件。NumPy/SciPy show_config提示可安装pyyaml仅影响展示，不需安装；保持原环境。

Codex本地合成验证已通过，报告位于/workspace/paper1-synthetic-runtime-probe.json；不是历史冻结生成主机报告，也不是服务器实际结果。不得把探针差异用作更改hash、容差、冻结数组、数据划分或自动放行训练的理由。
