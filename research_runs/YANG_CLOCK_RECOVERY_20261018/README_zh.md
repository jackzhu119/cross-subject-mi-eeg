# Yang 时钟故障的隔离恢复补丁（2026-10-18）

## 结论与边界

实际失败为 sub-001/ses-02：信号头 `22.03.19 15.03.13`、事件头
`22.03.19 15.03.12`。这不是时区/字符串空白问题。原程序要求两头字节相同，
但作者提供的 Neuracle 单信号文件导入器使用 TAL 的秒数直接计算事件位置，
不使用事件文件与信号文件的头时间差。不能从头差推出事件应平移一秒。

本版替代初版单文件例外，固定**全部153配对、306个文件**的路径、字节数、
完整SHA256、头SHA256及原始日期时间。生产清单SHA256：
`aa0c90e91e6a1dd876673db7319a067646d8604536d879b58b09b739d344f89f`。
91对时钟相同、61对信号头晚1秒、sub-034/ses-02晚2秒；所有配对日期相同。

运行时先由原有VerifiedFiles完整读取每份原始文件、校验下载回执，再把已验证身份
与固定生产清单比对。等时钟的91对同样需要身份匹配，不能绕过。未知输入、
不同文件配对、大小/内容SHA/头SHA/日期/时间变化均停止。没有普遍时间容差。

对固定v5文件使用作者单信号文件TAL导入约定，所有事件偏移量均为0秒。
不设置“允许一秒/两秒”的一般规则。每个session的events.clock_policy保留完整
配对身份、两头原始时间、差值、规则来源及生产清单SHA。该约定不是独立物理同步证明。
原 marker+[2,4) 窗口、[0,6)上下文、研究配置、模型和统计方案均不变。

真实证据范围明确区分：

- 两次153配对头报告字节完全一致，141210 bytes，SHA256
  `1e33e10db313df6b256200b9a6aceb3c499e3ad5254bb32a13efd8567d3410cd`。
- 124个差异文件在现场重新完整读取27,609,173,212 bytes，全部MATCH。
  回执70241 bytes，SHA256 `86d52a530aa171e8c74455248f1f1e265c4c7ed8c1c1696741a52bd5b3152817`。
- 其余182个文件的身份来自原下载回执公开字段投影，**不是本轮fresh全读**。
  投影68346 bytes，SHA256 `1b7b49a7f29911209b3e79665fab1fd5bf86dced24f4a54a5f1f8d37b437a5f7`。
  父下载回执SHA256 `7cc4e80645519fd3ec62027ef1c165f65d281d90bd0741ca8d7186e08ccf12ad`。
  所有306个文件均须在实际预处理时由VerifiedFiles重新完整校验。
- 本环境成功落地两个Library包并核对完整内容SHA及包内成员；124项fresh回执
  与原下载投影逐条一致。没有在本环境重读27.6GB原始信号。
- 独立公开v5事件成员回读仍见 `event_readback.json`：200个任务事件、每类100、
  首166.634秒、末2151.278秒。不声称GPU训练、全量预处理或真实结果备份已完成。

`freeze_yang_clock_registry.py` 可由原头报告、原下载回执公开投影、固定ZIP成员清单
及124文件fresh回执复现生产清单；输入均有明确内容哈希门禁，拒绝覆盖目标。
生产清单复制到新副本config/，纳入执行身份及最终provenance导出。

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
  /workspace/paper1_expansion/code_clockfix_v2_20261018
```

生成器在写入前验证全部原公开清单文件SHA，拒绝既有目标，不运行训练。
现场科学文件必须先与以下原版SHA匹配（已由主线程提供并在本地对应核实）：
`p1_data.py=d4d166e6cc9d5f674f65a3227dfa02b158b9ce8b5bcdb17b8b5d7a9d4f459ba1`；
`p1_runner.py=57d3501e43f8c43b6cd611b710b4a22f5c17f200a15f0819d2c15ae9f9adbe12`。

全153session头差异筛查已完成，不必重跑来代替进度。
现场接下来用现有锁定venv，对新副本执行 `load_yang_subject(1, ...)`，
核对600试次、每类300、三个session的 `clock_policy`。该检查不训练、不写原缓存。
确认通过后再执行完整原计划，后续所有原始文件会在预处理时逐个全读校验。

```bash
/workspace/paper1_expansion/venv/bin/python \
  "$PUBLIC_CHECKOUT/research_runs/YANG_CLOCK_RECOVERY_20261018/verify_yang_person.py" \
  --code /workspace/paper1_expansion/code_clockfix_v2_20261018 \
  --raw-yang /workspace/paper1_expansion/data/raw/yang --subject 1
```

此命令只在内存预处理，不写原缓存；若需要单独验证唯一两秒差配对，可改为 `--subject 34`。


科学模块变更会改变执行身份，**不能修改旧execution_identity来绕过恢复门禁**。
新副本默认使用 `runs/expansion18_clockfix_v2_20261018` 和
`data/processed18_clockfix_v2_20261018`，原失败运行与9个BNCI旧缓存原样保留。
原版缓存校验绑定整个数据模块SHA，因此本补丁不伪称旧缓存与新模块身份相同；
新的预处理会重新生成缓存，但不重复任何已完成神经训练（现场未发现检查点）。
新副本仍从原data/raw读取并完整校验下载回执，已验证原始成员可复用。

只有现场确认无训练worker、上述检查通过后，由同一操作者持有原launch.lock
运行新副本 `p1_runner.py --root /workspace/paper1_expansion --run-name expansion18_clockfix_v2_20261018`，
stdout追加到单独 `run_clockfix_v2_20261018.log`。不要运行START_ALL或替换原bootstrap。

现有归档watcher固定观察旧run路径；本次遵从用户限制**未改动它**。
新run未来完成不等于已自动归档，需要后续单独核对并明确处理该路径衔接；
不能把旧watcher存在当成新run归档保证。

## 本地检查

`python3 -m unittest discover -v -s research_runs/YANG_CLOCK_RECOVERY_20261018 -p test_recovery.py`

7项针对性测试通过，覆盖全部真实153配对（91/61/1）、零事件平移、改变身份/头字段拒绝、
错配和未知身份拒绝、不完整/重复/不同日期清单拒绝、独立副本完整清单与原目录保持。
另对生成副本运行5项合成数据路径回归（不训练、不下载）。
尚未运行现场600试次预处理、GPU训练或GitHub/R2结果回传。
原归档改造草稿已暂停并移出仓库，本提交只含独立科研恢复包。
