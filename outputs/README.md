# Output contract

每次真实运行使用唯一 `experiment_id`，并保存：

```text
outputs/<experiment_id>/
├── config.json
├── environment.txt
├── data_audit.json
├── split_manifest.csv
├── metrics.json
├── subject_metrics.csv
├── predictions.csv
├── figures/
└── run.log
```

并非每个阶段都会产生所有文件，例如 Phase 1 结构检查没有 `metrics.json`。失败运行也应保留日志或在 Research Log 中明确引用，避免只保留最好的结果。

