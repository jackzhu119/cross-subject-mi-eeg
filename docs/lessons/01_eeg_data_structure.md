# 第一课：EEG 数据的基本结构

这节课的目标不是训练模型，而是能回答：**一段连续、多通道的脑电，如何变成带标签的运动想象 trial？**

## 1. 先建立一张数据地图

EEG 原始数据可以先想成一张随时间不断向右延伸的表：

```text
                 time sample →
channel Fz       x x x x x x x ...
channel C3       x x x x x x x ...
channel Cz       x x x x x x x ...
channel C4       x x x x x x x ...
...
event                 ↑ cue: left_hand
```

用 NumPy 表示，连续数据通常是：

```text
(n_channels, n_times)
```

从多个事件周围切出等长片段后，epochs 通常是：

```text
(n_epochs, n_channels, n_times)
```

MNE 官方文档也使用这个 epochs 形状定义。

## 2. Channel：在哪里测到的信号

一个 EEG channel 通常对应一个电极位置与参考方式所形成的电位差时间序列。它不是“一个神经元”，而是头皮某位置对大量神经活动的混合观测，还会混入眼动、肌电和环境噪声。

科研中必须同时记录：

- channel name，例如 C3、Cz、C4；
- channel type，例如 EEG 或 EOG；
- electrode montage，即电极空间位置；
- reference 和 ground；
- channel order。

为什么与后续有关：CSP 学到的是多个 channel 的加权组合，即空间滤波器。如果 channel 顺序错了、训练测试通道不一致，空间滤波结果就失去含义。

### BNCI2014_001 中的 channel

- 22 个 EEG channel。
- 3 个 EOG channel，用于观察或处理眼动伪迹。
- 官方说明要求 EOG 不作为分类信息使用，所以后续模型特征只用 EEG。
- 记录时左乳突作为 reference，右乳突作为 ground。

初期会特别观察 C3、Cz、C4 一带，因为它们覆盖感觉运动皮层附近，但实验仍保留全 22 EEG 通道作为基准，不凭直觉提前删除通道。

## 3. Sampling rate：每秒测多少次

Sampling rate（采样率）记为 $f_s$，单位 Hz。250 Hz 表示每个 channel 每秒记录 250 个数：

```text
采样间隔 Δt = 1 / 250 s = 0.004 s = 4 ms
```

若一个 epoch 长 4 秒，概念上约有：

```text
250 samples/s × 4 s = 1000 samples
```

实际数组可能因为软件是否同时包含左右端点而出现 1000 或 1001 个时间点，不能只靠心算，必须打印 `epochs.get_data().shape` 核对。

Nyquist 定理告诉我们，在理想条件下，250 Hz 采样率能表示的最高频率是 125 Hz。数据采集时已做 0.5–100 Hz band-pass 和 50 Hz notch，因此原始记录本身已经带有硬件/采集预处理历史；后续数字滤波仍需单独记录，不能只写“做了滤波”。

## 4. Event：时间轴上的关键标记

Event 不是一段 EEG，而是“某件事在什么时候发生”的标记，至少包含：

- onset / sample position：发生时间；
- event code 或 description：发生了什么；
- 有时还包含 duration。

BNCI2014_001 原始 GDF 的关键事件码包括：

| 原始码 | 含义 |
|---:|---|
| 768 | 一个 trial 开始 |
| 769 | 左手 cue onset |
| 770 | 右手 cue onset |
| 771 | 双脚 cue onset |
| 772 | 舌部 cue onset |
| 1023 | 专家标记的 rejected/artifact trial |
| 32766 | 新 run 开始 |

MOABB 会把分类标签以更易读的名称暴露，例如 `left_hand`、`right_hand`、`feet`、`tongue`。写代码时不要假设标签编号永远相同，应保存并打印当前 `event_id` 映射。

## 5. Epoch：围绕 event 切出来的等长片段

Epoch 是从连续 EEG 中，以某类 event 为时间零点截取的一个时间窗。例如把 cue onset 设为 0 秒，截取后续 0–4 秒：

```text
continuous Raw
───────────────●════════════════●──────────────
             cue              cue + 4 s
               └──── epoch ────┘
```

一个 epoch 是“一个 trial 的多通道时间片”，不是平均波形。分类时每个 epoch 通常对应一个样本。

BNCI2014_001 的单 trial 时间线是：

- `t = 0 s`：出现 fixation cross，并有短提示音；
- `t = 2 s`：出现方向 cue，持续 1.25 秒；
- cue 出现后开始运动想象；
- `t = 6 s`：fixation cross 消失，运动想象结束。

因此从 cue onset 到 trial 结束是 4 秒。MOABB 的数据集页面也把任务窗概括为 4 秒。我们的最终 epoch 窗口会在 baseline 协议中明确冻结；现在先理解时间参考，不急着把某个窗口当成唯一正确答案。

## 6. Artifact：不是目标脑活动的干扰

常见 artifact 包括眨眼、眼球运动、咬牙/面部肌电、电极接触不良和突发大幅噪声。它与 event/epoch 的关系是：

- artifact 可以出现在连续 Raw 的某段时间；
- 若它污染某个 trial，就可能需要标记或排除该 epoch；
- “删除了多少 trial、按什么规则删除”必须成为实验结果的一部分。

BNCI2014_001 提供了 3 个 EOG channel，并有专家标记的 artifact trial。我们不会先把所有大幅信号盲目删掉，也不会把 EOG 当作分类特征；先审计 MOABB 当前加载方式对这些标记的处理。

## 7. BNCI2014_001 的完整层级

官方数据集结构：

```text
9 subjects: A01 ... A09
└── 2 sessions / subject（不同日期）
    └── 6 runs / session
        └── 48 trials / run
            ├── 12 left hand
            ├── 12 right hand
            ├── 12 both feet
            └── 12 tongue
```

所以每个 session 理论上有 288 个四分类 trial。只取左手与右手时，每个 session 理论上是 144 个二分类 trial；每名 subject 两个 session 理论上是 288 个二分类 trial。真实建模数量可能因 artifact 规则而减少，必须从实际加载结果统计，不能把理论数量直接写成最终样本量。

原始文件命名类似：

- `A01T.gdf`：Subject 1 的 training session；
- `A01E.gdf`：Subject 1 的 evaluation session。

竞赛当年 evaluation 标签曾被隐藏；现在通过公开数据和 MOABB 可以进行离线研究。`T/E` 的历史命名不要简单等同于我们未来所有实验的 train/test。做 LOSO 时，外层测试单位是完整 subject，而不是文件名中的 `E`。

## 8. 与三种泛化设置的对应

| 设置 | 训练/测试边界 | 回答的问题 |
|---|---|---|
| Within-subject | 同一 subject 内划分，通常保持 session/run 结构 | 模型能否适应这个人？ |
| Cross-session | 同一 subject 的一个 session 训练，另一个 session 测试 | 跨日期是否稳定？ |
| Cross-subject | 某些 subjects 训练，完整未见 subject 测试 | 换一个人还能否工作？ |

关键警告：把所有 trial 混在一起随机切分，会让同一个人的信号同时进入训练和测试。这可以是某种 within-subject 混合评估，但绝不能称为 cross-subject generalization。

## 9. 后续实际代码会检查什么

`scripts/inspect_bnci2014_001.py` 分两步工作：

1. 默认只查看数据集声明，不下载数据；
2. 加 `--load-data --subject 1` 后，真实读取一个 subject，逐个列出 session/run、channel types、sampling rate、数据形状和 annotation 计数，并保存 JSON 摘要。

第一轮真实检查的合格标准不是得到准确率，而是回答：

- 真实对象里有多少 channel，各是什么类型？
- 每个 session/run 的 sampling rate 是否一致？
- annotation 名称与数量是什么？
- MOABB 是否已经忽略或保留 artifact 标记？
- 左/右手 trial 的理论数量与实际数量差多少，为什么？

## 10. 本节自测

1. 250 Hz 表示什么？采样间隔是多少？
2. event 和 epoch 的本质区别是什么？
3. 为什么 epochs 常见形状是 `(trials, channels, time)`？
4. 为什么 EOG 对伪迹处理有用，却不应直接成为本数据集的分类特征？
5. 为什么随机拆分 trial 不能证明 cross-subject generalization？

## 官方资料

- [BCI Competition IV Dataset 2a 官方说明](https://www.bbci.de/competition/IV/desc_2a.pdf)
- [MOABB: BNCI2014_001](https://moabb.neurotechx.com/docs/generated/moabb.datasets.BNCI2014_001.html)
- [MNE: Raw 数据结构](https://mne.tools/stable/auto_tutorials/raw/10_raw_overview.html)
- [MNE: Epochs 数据结构](https://mne.tools/stable/auto_tutorials/epochs/10_epochs_overview.html)

