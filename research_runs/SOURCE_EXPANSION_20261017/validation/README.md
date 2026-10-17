# 验证记录的阅读范围

这些记录是代码与数据读取的质量检查，不是论文实验成绩。所有模型拟合、预测和统计闭环测试使用合成输入；真实 EEG 仅执行读取、预处理和缓存复用检查。

- `clean_cpu_repro_checks.json`：干净 managed Python 3.12.12；72 个非 GPU 依赖版本逐一匹配生产 CUDA lock；torch/torchaudio 是明确的 CPU 构建。37 项数据、选择器、训练恢复、runner 及 CSP 核心检查通过。
- `clean_cpu_pyproject.toml` 和 `clean_cpu_uv.lock`：复现上述 CPU 环境的独立文件，不用于正式 GPU bootstrap。
- `csp_task_and_download_checks.json`：后续传统模型编排、源冻结门禁和稳定下载清单的 8 项回归检查。
- `bootstrap_installer_review.json`、`bootstrap_launcher_review.json`：实测固定 uv wheel 和二进制 SHA、重复校验、managed Python 路径；用无害 worker 验证后台单实例及锁。该轮记录的 bootstrap 哈希早于随后增加的 CSP 自测调用，既有安装器与启动逻辑未再修改。
- `bnci_real_preprocessing_validation.json`：一个 BNCI 人员、两次会话，288 个不同左右手试次。
- `dreyer_real_preprocessing_validation.json`：一个 Dreyer 人员、两次 acquisition，80 个不同左右手试次；没有模型预测。
- `runner_real_cache_resume_check.json`：上述两个真实人员的缓存复用，无重建。
- `yang_event_validation.json`：完整小事件文件、200 个 1/2 类标记，未读取全量信号。
- `yang_first_real_context_qc.json`、`yang_one_trial_current_contract_validation.json`：一个真实 Yang trial 的原生上下文与生产预处理检查。没有完整被试处理、完整 EEG 压缩成员 CRC 或全 ZIP MD5 验证。
- `eegnet_library_cpu_smoke.json`、`csp_synthetic_validation.json`：官方 EEGNet 数值与传统模型核心验证。

各 JSON 的源码哈希描述其执行时的版本。交付前整包的最后一次 CPU 测试在 `final_cpu_checks.json`，其中列出最终源码哈希。`report_export_validation.json`记录报告导出的3项独立检查；下载安装器的9项测试也包含在最后57项整包测试内。

没有执行 RunPod GPU 完整安装、全数据集处理或 108 条正式神经训练。真实任务会在固定下载和样本完整性检查通过后开始；任何错误会明确停止，既有数据和检查点保留。
