# Test plan

正式实现开始后，优先加入以下回归测试：

- channel order 在 train/test 间一致；
- epochs 的维度顺序是 `(trials, channels, time)`；
- subject 级切分不存在重叠；
- scaler、CSP、feature selection 只在训练折 `fit`；
- 固定 seed 的切分与结果可重复；
- 每个预测都能追溯到 subject/session/run/trial；
- theoretical trial count 与 artifact 处理后的实际 count 都被记录。

