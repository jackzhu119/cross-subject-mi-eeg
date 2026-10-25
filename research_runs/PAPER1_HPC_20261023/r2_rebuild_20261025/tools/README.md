# 论文1冻结数据恢复与R2归档

仅从官方来源传输并校验原始字节；不运行信号处理、训练、预测、统计或学校Slurm。
固定仓库提交 `23aec28407468b5d3d4b9b15450e84dc616bfd54`，使用现有checkout，不创建worktree、不修改冻结文件。

## 本次实际结果

- Python 3.12.14，初始本机可用约30,306,684,928字节，采用逐文件下载、校验、上传及完整回读。
- 官方Yang原文件51001884的1字节Range返回206，并核对ZIP总长65,630,556,299字节；没有下载完整ZIP或声称完整ZIP MD5已验证。
- 现有绑定已注入；桶变量为`E2_BUCKET`，作为`R2_BUCKET`兼容别名使用，不改变身份。
- 首次SDK构造遇到本环境无效AWS profile；独立显式R2 session修正后，70字节自有对象PutObject返回403/AccessDenied。尚未回读或删除，因为上传未成功。没有重试拒绝，也没有启动数据搬运。
- 数据完成0/504项、0/71,339,562,138原生字节；全部未完成项见`evidence/manifest.tsv`。403证据见`evidence/r2-probe-attempt2.json`。
- 此错误尚不能区分R2目标桶/权限、代理路由或连接配置问题。需在现有环境连接中修正实际写入授权后再作一次新测试；不要在聊天或Git中存密钥。

## 恢复操作

工具位于`/workspace/paper1-archive-tools`，状态及自有临时载荷位于`/workspace/paper1-archive-state`，原仓库保持不变。依赖通过本目录`requirements.txt`固定。

离线检查（不发网络、不处理科研数据）：

```bash
cd /workspace/paper1-archive-tools
.venv/bin/python transfer.py --preflight --offline
.venv/bin/python -m unittest -v test_r2_archive test_transfer
```

**只有在R2连接/权限有实际变更后**，执行新的小对象测试，保留旧失败证据：

```bash
cd /workspace/paper1-archive-tools
.venv/bin/python r2_archive.py probe --output /workspace/paper1-archive-state/r2-probe-after-fix.json
```

必须出现`probe_verified`，其中上传、流式SHA回读、删除及HEAD404都通过，才启动后台搬运：

```bash
cd /workspace/paper1-archive-tools
.venv/bin/python launch.py
.venv/bin/python launch.py --status
```

启动器与终端脱离，传输与GitHub报告各自独立。`transfer.py --run`仍会强制小对象测试作为gate；401/403停止对应传输。原文件续传、完整文件复用，逐文件回读通过后清理本机自有副本。每45秒记录实际源字节、上传字节、回读字节、当前文件及完成数；GitHub约每180秒同步，报告失败不停止传输。

## 冻结校验与归档

顺序Yang→BNCI→Dreyer。Yang只Range读取选中43,981,251,776压缩字节，逐成员字节解压后保留原目录SHA、306项原生SHA和6项元数据CRC契约，另外记录全部实际SHA。BNCI18份MAT和Dreyer174份nm000250/v1.0.5 EDF使用原SHA。

R2目标前缀`paper1-hpc-20261023/frozen-inputs-v1/`，子目录`yang/`、`bnci/`、`dreyer/`保留原相对路径，保存原生文件。成功证据是完整远端GET流的大小和SHA匹配；不以ETag、HEAD大小或请求接受作为完成。

`manifest.tsv`列出全部504项来源、预期大小、原SHA/CRC、实际SHA/CRC、对象key及状态。`completion.jsonl`保留成功/失败与远端完整回读证据；恢复时已归档对象也必须重新流式验证。Yang目录二进制保存在状态目录，目录SHA证明保存到清单证据。

GitHub只写专用分支`archive/paper1-frozen-inputs-20261025`下的新增`r2_rebuild_20261025/`目录；同步器固定文件白名单，不扫描原始载荷、凭据或进程日志，不改变main或固定checkout。
