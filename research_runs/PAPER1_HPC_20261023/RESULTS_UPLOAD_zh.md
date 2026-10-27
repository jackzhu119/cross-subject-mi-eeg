# 学校HPC：上传已完成的90项研究结果

2026-10-27核对运行分支 [`3746b1f0`](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/3746b1f02271a780b06d7cbeb6ef6b91ab64de76/hpc_status/paper1-risk-v1/status.json)：75项开发、15项最终训练均完成，失败0；三个统计域均为`complete`。主作业记录的完成时间为北京时间2026-10-27 02:27左右。

原自动同步器只发布`hpc_status/paper1-risk-v1/status.json`，其中的统计是经过字段筛选的摘要。它不上传完整人员指标、105份评价、预测分片或模型。因此，进度显示完成不等于完整研究证据已归档。

## 手动执行一次

**推荐后台方式：** 如果旧的前台上传还占着终端，先在那个窗口按`Ctrl+C`，仅结束前台导出／上传，原结果与Slurm作业保持。然后在login1运行交付消息中的固定下载命令，并追加`--background --publish`。后台立即返回PID，可以关闭终端。已有同项目后台会复用；旧前台仍持有导出锁时，后台显示`waiting_existing_export`并等待，不强杀进程、不重复打包。

在学校 **login1** 下载本目录的 `PUBLISH_RESULTS_ON_SCHOOL.py`，使用现有Python执行：

```bash
/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python -B -u /tmp/paper1-publish-results.py --project /public/home/zhuziyuan/projects/paper1-risk-v1 --background --publish
```

交付消息提供固定commit的一行下载及执行命令。脚本只有Python标准库和系统curl依赖，不安装任何包，不需要GPU或新Slurm作业。它优先复用`config/sync.json`指向的私有token；没有现有token或追加`--reauthorize`时才隐藏询问，不把凭据写入代码或Git。

凭据输入在后台启动前完成，后台不等待终端输入。校验、哈希、打包、上传和完整回读分别记录阶段；每30秒写一次心跳及实际计数。日志追加保留，状态保存在共享项目目录：

```bash
tail -n 30 /public/home/zhuziyuan/projects/paper1-risk-v1/logs/results-upload.log
```

```bash
cat /public/home/zhuziyuan/projects/paper1-risk-v1/state/results_upload_status.json
```

脚本会：

1. 只读核对75＋15任务、每项40轮／5120更新、完成身份、源选轮与三域完整统计。
2. 从完成记录精确选择105个最终评价目录，打包原JSON及对应预测分片；不扫描全部训练期评价。
3. 在`paper1-risk-v1/exports/github-results/`生成确定性压缩包和完整文件SHA256清单。
4. 上传到独立分支 **`hpc-results/paper1-risk-v1`**，目录为`research_runs/PAPER1_HPC_RESULTS_20261027/<包SHA前16位>/`；不修改main中的论文、旧结果或运行分支。
5. 按不可变commit核对上传条目，再完整GET回读压缩包并核验SHA256。

成功标志：**`RESULT_BUNDLE_PUBLISHED_AND_READBACK_VERIFIED`**，同时输出commit和可打开的结果目录URL。

临时断网、超时、服务端5xx或明确限流会自动退避重试，直接复用本次已生成的压缩包，不重新校验／打包全部文件。已上传的Git对象按内容去重，分支更新不强推。真正的401/403授权拒绝、SHA错误或本地数据问题会明确停止，不循环掩盖；授权问题可用同一后台命令加`--reauthorize`重新隐藏输入。此命令不会恢复、重跑或取消任何训练。

## 包含与保留范围

| 包含的原始结果文件 | 用途 |
|---|---|
| `config/study.json`、`tasks.json`、`state/plan.json`、`state/selection.json` | 固定研究设置、任务与源选轮证据 |
| 90份`complete.json` | 完整训练轨迹计数、实际运行版本和各评价引用 |
| 105份指定评价`summary.json` | 75份源外层评价＋15×2份Dreyer评价 |
| 这些评价目录中的`.npz` | 保存的logits、真实标签、trial ID和模型身份，用于之后独立数值核验 |
| 7份`outputs/analysis/*.json` | 三域人员指标、完整统计、设置及来源绑定 |
| `EXPORT_MANIFEST.json` | 每个导出成员的长度、SHA256及核验范围 |

原始EEG、prepared输入、模型／优化器checkpoint、凭据及训练期`inner_epoch_*`分片不上传。**保留学校原项目和全部模型权重**；结果包不是完整模型备份。

导出过程不解码预测数组、不重新算统计或运行模型。SHA和回读证明上传字节完整，科学结论仍需对保存预测、人员指标、选择过程及统计做独立复核。所有比较方向原样保留。
