# Notebook policy

Notebook 用于教学、快速检查和可视化探索，不作为最终实验的唯一实现。

命名建议：

```text
01_raw_and_events.ipynb
02_filtering_and_psd.ipynb
03_epoch_extraction.ipynb
```

一旦逻辑需要重复运行或参与正式实验，应迁移到 `src/mi_eeg/`，由 `scripts/` 调用，并把参数与结果写入 `outputs/<experiment_id>/`。

