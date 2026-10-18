# Yang 时钟故障的隔离恢复补丁（2026-10-18）

## 结论与边界

实际失败为 sub-001/ses-02：信号头 `22.03.19 15.03.13`、事件头
`22.03.19 15.03.12`。这不是时区/字符串空白问题。原程序要求两头字节相同，
但作者提供的 Neuracle 单信号文件导入器使用 TAL 的秒数直接计算事件位置，
不使用事件文件与信号文件的头时间差。不能从头差推出事件应平移一秒。

本补丁只为**完整 SHA256 已核验的这一文件对**采用作者导入约定，并记录审计。
不设置“允许一秒”的普遍容差，不删除所有时钟校验，不平移 TAL。
其他不一致文件对继续失败。不能据此声称设备物理同步已独立验证。
原 marker+[2,4) 窗口、[0,6)上下文、研究配置、模型和统计方案均不变。

现场主线程提供的六文件完整 SHA 与下载回执一致；本环境额外从公开固定v5
重新下载整个 ses-02 事件成员，检查 ZIP CRC 与 SHA256，独立得到200个任务事件、
两类各100，首166.634秒、末2151.278秒。详见 `event_readback.json`。
本环境没有重新下载/读取整个信号文件；没有开训、访问Pod或完成真实备份。

## 直接来源证据

公开固定包：<https://ndownloader.figshare.com/files/51001884>，对应
<https://doi.org/10.25452/figshare.plus.22671172.v5>。
本次通过项目固定中央目录SHA256检查后，选择性读取这些小成员，**未下载或校验整个ZIP**：

- `code/pre-processed/preprocessed.m`：1149 bytes，SHA256
  `3aa23e802ed1c3ed117abfe404ca47fdf756ddabfdfb51c7242abbedabc619d4`。
  作者调用 `readbdfdata` 导入一对 data/evt 文件。
- 同目录 `README.md`：215 bytes，SHA256
  `ca105f50f0276dcc7de5245019c691c917cc6e6fe4eb5c54b8a411dde0cba51a`，
  指明使用随包 Neuracle1.1。
- 同目录 `Neuracle1.1.rar`：8052 bytes，SHA256
  `829cfc32c836d1ac9f85ae540835d1f177ea214a57cbd9e8278ac997f33c713a`。
- 从上述RAR完整提取 `Neuracle1.1/readbdfdata.m`：21737 bytes，SHA256
  `dd6acba71429ba029dd6d6fe29e9eaf1a9d51233fc484dbca87e63bd624dd18f`。
  第124–137行读取evt，使用TAL offset ×信号采样率；138–139行仅多信号文件进入偏移修正。
  第425–441行说明offset来自TAL自身，而非记录头日期时间。
  本次未执行MATLAB/EEGLAB；以上为真实作者代码的静态逻辑核查。

厂商当前代码交叉支持同样的单文件约定：
<https://github.com/neuracle/neuracle-eegfile-reader/blob/95fe83fa9d884df9ed1b62f3fa71e159e9aa2768/readbdfdata.m>。
恢复依据是随数据版本提供的导入器，不能以移动的最新厂商代码替代它。

## 应用（仅唯一现场操作者执行）

**不读取或复制服务器旧code中的自定义配置/秘密；不修改code、_archive、凭据或上传配置。**
先从此研究分支的固定提交取得干净公开仓库到新目录。下例 `PUBLIC_CHECKOUT`
必须指向该干净公开检出，不能指向用户原始服务器code目录。

```bash
python3 "$PUBLIC_CHECKOUT/research_runs/YANG_CLOCK_RECOVERY_20261018/build_reviewed_copy.py" \
  "$PUBLIC_CHECKOUT/research_runs/SOURCE_EXPANSION_20261017" \
  /workspace/paper1_expansion/code_clockfix_20261018
```

生成器在写入前验证全部原公开清单文件SHA，拒绝既有目标，不运行训练。
现场科学文件必须先与以下原版SHA匹配（已由主线程提供并在本地对应核实）：
`p1_data.py=d4d166e6cc9d5f674f65a3227dfa02b158b9ce8b5bcdb17b8b5d7a9d4f459ba1`；
`p1_runner.py=57d3501e43f8c43b6cd611b710b4a22f5c17f200a15f0819d2c15ae9f9adbe12`。

先用 `diagnose_yang_clocks.py <data/raw/yang>` 做全153session头检查，把不匹配对
交给复核；该脚本只读头，不能替代完整文件SHA。未审阅的新差异仍是启动阻塞。
随后使用现有锁定venv，对新副本运行 `load_yang_subject(1, ...)` 的源数据预处理验证，
核对600试次、每类300、记录 ses-02 的 `clock_policy`。该检查不训练、不写原缓存。

科学模块变更会改变执行身份，**不能修改旧execution_identity来绕过恢复门禁**。
新副本默认使用 `runs/expansion18_clockfix_20261018` 和
`data/processed18_clockfix_20261018`，原失败运行与9个BNCI旧缓存原样保留。
原版缓存校验绑定整个数据模块SHA，因此本补丁不伪称旧缓存与新模块身份相同；
新的预处理会重新生成缓存，但不重复任何已完成神经训练（现场未发现检查点）。
新副本仍从原data/raw读取并完整校验下载回执，已验证原始成员可复用。

只有现场确认无训练worker、上述检查通过后，由同一操作者持有原launch.lock
运行新副本 `p1_runner.py --root /workspace/paper1_expansion --run-name expansion18_clockfix_20261018`，
stdout追加到单独 `run_clockfix_20261018.log`。不要运行START_ALL或替换原bootstrap。

现有归档watcher固定观察旧run路径；本次遵从用户限制**未改动它**。
新run未来完成不等于已自动归档，需要后续单独核对并明确处理该路径衔接；
不能把旧watcher存在当成新run归档保证。

## 本地检查

`python3 -m unittest discover -v -s research_runs/YANG_CLOCK_RECOVERY_20261018 -p test_recovery.py`

6项通过：等时钟保持原行为、精确核验例外不移事件、其他SHA/时钟拒绝、其他一秒差拒绝、
新副本完整清单哈希/原版保持/窗口配置保持/拒绝覆盖、无归档配置操作。
尚未运行全量科学测试、实际600试次预处理、GPU训练或GitHub/R2结果回传。
原归档改造草稿已暂停并移出仓库，本提交只含独立科研恢复包。
