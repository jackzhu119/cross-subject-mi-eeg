# 18/18恢复后的只读源数组诊断

此步骤由父对话统一执行，不与正在进行的v2恢复并发启动。前置条件：新supervision退出0，transfer显示18/18完整文件大小与冻结SHA256一致。路由合法或原始MAT匹配均不代表历史数组问题解决。

## 原始HEAD证据补充

独立从私有Library回读原始527字节JSON，SHA256为081587efbac143806c475cfc5632d199a7de36ea478325a3ffe306b201c97955。原字节及独立核验记录保存在prior_failure_20261014T105918Z下。记录显示2026-10-14T11:02:38.143558+00:00，A01E原址HEAD302、精确同名lampx Location、未跟随、curl退出0、默认代理保留。未重新发起HEAD；其余17项路由未知，MAT正文未经此记录证明。此前失败证据和当时仅收到父对话报告的记录保持原样，以此追加证据更新。

## 固定代码与旧基线

诊断代码固定c802e65709103189becf7e6ff3a55c99a405a7e8；科学基线固定eae194514def23e5d1ec6cbb117d4f84fc6f067f。基线是诊断提交祖先；本Codex已核对诊断器所校验的六个科学文件在两个提交中全部逐字节一致。

以下在全新目录创建独立checkout，避免修改现有bootstrap和下载目录。完整克隆保留旧Git对象，不使用depth=1或GitHub ZIP。目录已存在时停止并检查，不能删除重建来规避历史记录。GitHub获取仅是代码，无EEG下载。

```bash
set -euo pipefail
test ! -e /workspace/paper1-source-diagnostic-c802
git clone --no-checkout --single-branch --branch research/paper1-handoff-20261014 \
  https://github.com/jackzhu119/cross-subject-mi-eeg.git \
  /workspace/paper1-source-diagnostic-c802
cd /workspace/paper1-source-diagnostic-c802
git cat-file -e c802e65709103189becf7e6ff3a55c99a405a7e8^{commit}
git cat-file -e eae194514def23e5d1ec6cbb117d4f84fc6f067f^{commit}
git merge-base --is-ancestor eae194514def23e5d1ec6cbb117d4f84fc6f067f c802e65709103189becf7e6ff3a55c99a405a7e8
git checkout --detach c802e65709103189becf7e6ff3a55c99a405a7e8
test "$(git rev-parse HEAD)" = c802e65709103189becf7e6ff3a55c99a405a7e8
test -z "$(git status --porcelain)"
```

若克隆失败，保存错误；不得改用无基线对象的ZIP或修改verify_science绕过检查。使用已有GitHub授权，不写新持久凭据。

## 精确运行命令

使用已验证的现有诊断runtime，不重新安装：NumPy2.3.5、SciPy1.17.0、pandas2.2.3；已有boto3供模块导入使用。命令不带--import-r2，不访问R2，不训练、不生成目标预测。数据目录和输出均在checkout外。读取本地18项MAT后会再次检查原始文件哈希，重建2592条源样本并与冻结逐样本和整体哈希比较；六个科学文件先通过Git旧基线逐字节检查。任何失败停止，不重置冻结记录或修改容差。

```bash
set -euo pipefail
cd /workspace/paper1-source-diagnostic-c802
test ! -e /workspace/paper1-readonly-probe/new-host-source-report.json
test ! -e /workspace/paper1-readonly-probe/new-host-source-diagnostic.log
test ! -e /workspace/paper1-readonly-probe/new-host-source-diagnostic.exit-code
set -o noclobber
set +e
/workspace/paper1-diagnostic-runtime/bin/python \
  research_runs/REDESIGN_CLOUD_20261013/scripts/reconstruct_source_readonly.py \
  --data-dir /workspace/paper1-readonly-probe/data \
  --output /workspace/paper1-readonly-probe/new-host-source-report.json \
  > /workspace/paper1-readonly-probe/new-host-source-diagnostic.log 2>&1
diagnostic_exit=$?
set -e
printf '%s\n' "$diagnostic_exit" > /workspace/paper1-readonly-probe/new-host-source-diagnostic.exit-code
cat /workspace/paper1-readonly-probe/new-host-source-diagnostic.log
exit "$diagnostic_exit"
```

报告已存在时不覆盖或重复实验，先回传。进程中断或退出非零时先保存log及退出码；异常发生在报告生成前可能没有JSON，不能虚构报告。若进程仍运行，不另启一次。诊断需要保存MAT约780MB和内存数组；服务器62GB内存足够，保持传输要求的6GiB空闲余量，不在30GB容器盘复制另一套MAT。

## 结果解释与离机交接

- 退出0且NEW_HOST_SOURCE_INPUTS_MATCH：本新主机本次源输入匹配，不证明历史主机数组差异根因，也不自动授权训练。
- 退出2且NEW_HOST_SOURCE_INPUT_MISMATCH_BLOCKED：保留actual/expected array_hashes、per_trial_mismatches、filter_coefficients、标签/元数据/ID检查和CPU特性，继续定位；不调容差。
- 其他异常：以log和退出码定位运行环境/文件问题；未写JSON时仍需回传日志。

父对话离机保存v2 transfer/supervision/worker日志、一次性登记、原始HEAD及旧失败证据、诊断JSON（若有）/日志/退出码，并生成完整大小SHA256清单。独立回读核验后才允许关机。原始MAT仍在私有缓存，禁止进入公共Git仓库。本Codex没有启动此诊断或其他下载/训练任务。
