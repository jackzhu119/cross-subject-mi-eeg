# Q5 云端执行状态

日期：2026-09-23。研究协议见 `configs/q5_e001_eegnet.json`，云端说明见 `README_CLOUD.md`。

## 已核实状态

- Q5 训练进度：0/9 外层 LOSO folds、0/36 source-inner validation fits、0/27 full-source seed fits。
- 本机首轮启动在 EEGNet 构造参数校验时报错，在首个 forward/training epoch 前结束。具体错误与原始代码快照保留在 `results/Q5-E001/`；没有 Q5 训练检查点或分类成绩。
- 修正后的 CPU 模型接口 smoke check 通过：输入 `(batch, 22, 750)`、输出 `(batch, 4)`、2,932 个参数，交叉熵反向传播成功。
- Q5 receipt validator 的 5 个合成收据单元测试通过。它验证验证器逻辑，不代表 Q5 实验通过。
- 用户将正式 Q5 训练转移至云端。本机未运行正式 Q5，也没有执行任何 CUDA 检测或 GPU 运算。

## 云端环境选择

截图显示服务镜像信息为 Python 3.12 / PyTorch 2.13 / CUDA 13.2，并展示 V100S。PyTorch 官方兼容矩阵说明 CUDA 13.x 预构建包不再支持 Volta（V100，compute capability 7.0）；PyTorch 2.14 的 CUDA 12.6 构建仍保留 Volta 支持。CUDA 12.6 的 Python 3.12 Linux x86_64 wheel 已由官方索引发布。CUDA 12.6 也覆盖本项目此前指定的 RTX 4090/Ada 环境。为匹配本机 PyTorch 2.14 版本并兼容截图中的 V100S，云包安装 `torch==2.14.0`、官方 CUDA 12.6 wheel 与 `braindecode==1.5.1`。

实际设备是否可用由服务器上的 `python check_gpu.py` 检查。在服务器运行前，本项目没有声称该镜像能直接用于 V100S，也没有声称任何 GPU 验证已经通过。

## 启动与产物

1. 上传并解压 `Q5_EEGNet_Cloud_Ready.zip`。
2. 运行 `bash run_gpu.sh`。脚本安装云端依赖、检查实际 CUDA、按原配置续跑 Q5、完成后执行独立验证。
3. 新的 Q5 结果集中保存到 `results/Q5-E001/`，运行日志追加到 `logs/q5_gpu.log`。历史 P1–Q4 输出仍原样保存在 `outputs/`，用作基线与审计证据。

完整运行后仍须检查 `results/Q5-E001/status.json` 和 `validation_report.json`，然后才能更新论文结果。
