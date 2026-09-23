# Cross-Subject Motor Imagery EEG Decoding

中文题目：**基于空频特征与深度学习的跨被试运动想象脑电解码研究**

## 核心科研问题

如何在严格避免数据泄漏的前提下，提高运动想象 EEG 在不同受试者之间的泛化能力？

## 当前状态

- 更新时间：2026-09-23。已完成真实二分类传统基线、探索性空频/眼电实验、完整四分类九人 LOSO 传统对照与后续特征维数探索；Q4-E001 和 Q4-A001 均通过独立验证，详见 [四分类结果](docs/q4_e001_results.md) 与 [维数消融](docs/q4_a001_capacity_results.md)。
- 已完成：独立 Python 3.12 环境、18 个源 MAT 文件、Subject 1 结构审计、9 人 CSP+LDA/SVM、within-session / cross-session / LOSO、Welch PSD 空频消融、源拟合 EOG 回归、预测与源文件哈希核验。
- 当前边界：四分类已有一个真实的传统基线，但九频带方法平均没有超过宽频 LDA；没有确认创新性、没有 EEGNet 结果、没有外部数据集验证，也未达到投稿就绪。
- 权威进度入口：[Research Progress](docs/research_progress.md)、[文献矩阵](references/literature_matrix.md) 与 [研究定位](docs/research_gap_and_next_experiments.md)。现有两份论文样例保留为历史工作稿；正式写作入口改为 [paper outline](paper/outline.md)。
- 下一模型阶段已有 [EEGNet 源端验证协议草案](docs/q5_eegnet_protocol_draft.md)，尚未训练或产生分数。

## 目录导航

```text
configs/                 固定实验参数；每次运行复制到对应输出目录
data/                    数据说明；原始数据和处理中间物不提交版本库
docs/                    路线图、课程和实验协议
experiments/             全项目实验登记表
logs/                    Research Log
notebooks/               只做探索；稳定逻辑迁移到 src/
outputs/<experiment_id>/ 每次实验的参数、指标、预测、图和日志
references/              官方资料和论文索引
scripts/                 可直接运行的入口脚本
src/mi_eeg/              可复用研究代码
tests/                   数据形状、切分和泄漏防护测试
sources/                 ChatGPT 项目同步资料，只读
```

## 可复现环境

本项目已使用独立 Python 3.12 环境和 `uv.lock`。恢复同一依赖版本：

```powershell
uv sync --locked --python 3.12 --extra dev
.\.venv\Scripts\python.exe -m pytest -q
```

元数据检查：

```powershell
.\.venv\Scripts\python.exe scripts\inspect_bnci2014_001.py
```

Subject 1 真实结构检查（已有结果在 `outputs/P1-E001/`）：

```powershell
.\.venv\Scripts\python.exe scripts\inspect_bnci2014_001.py --load-data --subject 1
```

本机数据缓存位于 `data/raw/`，18 个 MAT 合计约 780 MB。重复实验请指定新的输出目录；不要覆盖既有结果。

完整四分类的固定实验配置和方法解释见 [Q4 配置](configs/q4_e001_fourclass_filterbank.json) 与 [傅里叶及滤波器组说明](docs/fourier_filterbank_lesson.md)。程序入口：

```powershell
.\.venv\Scripts\python.exe scripts\run_fourclass_filterbank.py --output-dir outputs\NEW-RUN-ID
.\.venv\Scripts\python.exe scripts\validate_fourclass_filterbank.py outputs\NEW-RUN-ID
```

`NEW-RUN-ID` 必须是一个尚无内容的新目录；实际运行的配置、代码快照与文件哈希保存在该输出目录。

## 科研底线

1. 先固定 research question、数据划分和主指标，再比较模型。
2. 受试者级测试集在建模全程不可见。
3. 标准化、CSP、特征选择和超参数搜索只能在训练数据内拟合。
4. 保存每个受试者的结果、均值、标准差和失败运行，不只保存最好结果。
5. 未真实运行的数据、图表和指标不得写成实验结果。

详细计划见 [ROADMAP.md](ROADMAP.md)，第一课见 [docs/lessons/01_eeg_data_structure.md](docs/lessons/01_eeg_data_structure.md)。
