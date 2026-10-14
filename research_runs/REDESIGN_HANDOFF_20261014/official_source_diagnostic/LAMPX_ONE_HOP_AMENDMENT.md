# 单次BNCI原址→精确同名lampx地址的传输修订

父对话明确授权此限定修订和一次新的有界恢复；由其现有Jupyter执行，本Codex未请求原始EEG、官网HEAD、目标数据或失败R2路径。既有科学输入/原始SHA256、大小、19通道、划分、seed、容差、预算、0 fits及旧数组错误根因未知全部保持。

## 失败证据与路由证据分开

本任务通过私人Library读取8032字节失败证据包，SHA256 `f7370a1105175d9cc6b62c85a06d92aec423bca99ef7ef97e999bc0a9da9e23e`；独立核对8个清单文件的大小/哈希、原脚本与7cb174437a72a8a636a3a4cdb0e9befb1745f597 Git字节一致。原attempt `20261014T105918Z-77294d31f0f5` 在A01E重定向限制处退出2，完成0/18，partial为0字节，未进行输入重建。原始包私有保留；无敏感原transfer/supervision/worker记录按原字节保存在prior_failure_20261014T105918Z，未改原文件。

另据父对话报告，服务器2026-10-14 11:02:38 UTC对原A01E地址的一次HEAD（不跟随、不取body）得到302，Location为 `https://lampx.tugraz.at/~bci/database/001-2014/A01E.mat`。本任务未独立发起该HEAD，也未收到其原始HTTP日志；只将其列为父对话实测报告。其他17项路由尚未验证，绝不标为已验证。官方页面/机构链接只支持路由来源背景；说明PDF列GDF并不证明MAT字节。真正内容证明仍是完整size/SHA256。

## 最小代码变化

旧脚本restore_source_official.py及旧manifest不改，新工具为restore_source_official_lampx_v2.py。

1. 请求始终从manifest里的冻结BNCI HTTPS URL开始，不能直接选择lampx镜像。
2. 原址直接200仍走原有精确字节校验；若发生重定向，仅允许原始GET响应的Location与唯一构造值完全相同：`https://lampx.tugraz.at/~bci/database/001-2014/<当前冻结文件名>`。限定18个A01–A09 × T/E MAT一对一，不接受其他扩展名。
3. 只允许一次标准HTTP重定向（301/302/303/307/308）；必须读取该次实际响应Location，不能把预先构造的目的地冒充已经观察到的路由。目标响应URL还须与记录的这一跳一致。
4. 拒绝任何后续跳转，包括返回原址、lampx内部再跳转；拒绝其他host、路径、query、fragment、端口变体、用户信息、跨文件和HTTP降级。TLS证书/主机校验保持，环境代理禁用。
5. 成功响应路由逐文件写入actual_response_routes，未观察项列入request_routes_not_observed；合法缓存复用不伪造本次HTTP请求证据。最终必须完整size、SHA256与冻结值一致。路由符合不等于原始文件通过，更不等于处理后输入通过。
6. 单worker、每缺失文件单次尝试、0自动重试、整次worker1800秒、终止宽限5秒保持。失败partial和attempt日志不覆盖、不删除。
7. --execute前要求旧transfer/supervision原字节哈希及旧0字节partial仍在指定原目录。核对后在同一data-dir排他创建`.official-lampx-v2-one-attempt.json`，绑定新attempt与v2脚本SHA。此登记即消耗唯一新尝试，启动结果不确定也不自动重试。再次启动因已有登记拒绝；不得删除登记或换缓存目录规避。内部worker还核对父登记与当前脚本SHA，不能靠worker参数另启未登记任务。

## 父对话执行

使用新固定提交下载v2脚本到独立新文件，核对交付SHA256；原脚本、manifest、旧日志和空partial保留。manifest仍是原文件，SHA256不变：`e553d65cd86e5309e077ccfea21a9bee6020c5d9d5040de12089c2b859770b86`。

在含v2脚本及原manifest的bootstrap目录，先同命令不带--execute做清单dry-run；随后只执行一次：

```bash
/workspace/paper1-diagnostic-runtime/bin/python restore_source_official_lampx_v2.py \
  --data-dir /workspace/paper1-readonly-probe/data \
  --evidence-dir /workspace/paper1-readonly-probe/official-transfer-evidence \
  --execute
```

不要先删除或搬走旧empty partial和两份旧JSON。未找到旧证据、已有v2登记、校验失败、网络失败或新域名/二跳均停止并回传记录，不放宽白名单。

只有新supervision退出0、transfer确认18个完整匹配，才按原交接使用c802e65709103189becf7e6ff3a55c99a405a7e8诊断代码和eae194514def23e5d1ec6cbb117d4f84fc6f067f科学基线运行本地缓存模式重建。该重建不带--import-r2；不训练、不访问目标。若完成，不得将此网站传输问题解释成旧`frozen_source_input_changed:array_hashes`根因。

## 验证边界

离线合成测试覆盖原字节/缓存/异常保留/超时等旧安全属性，以及允许的一跳、直接lampx请求拒绝、缺失真实Location拒绝、跨文件/host/路径/query/fragment/降级/第二跳拒绝、路由逐文件记录、一次登记与旧证据保留。实际17个路由和任何MAT正文均未由本任务请求。仅软件通过；实际传输仍由父对话执行并保存离机证据。
