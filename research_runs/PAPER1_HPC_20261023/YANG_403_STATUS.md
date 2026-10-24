# Yang学校GET403：最小定位入口

## 当前结论与实际下一步

学校补件已确认两条Python GET路线均在**入口**收到HTML403，无Location、无query，未到达S3；随后系统curl对相同公开入口也返回403。证据见`evidence/yang_school_route_rejection_20261024.json`。这排除了“只有Python客户端不兼容”的解释；当前入口拒绝不能用S3签名过期来解释。具体拒绝由学校网络、中间服务还是Figshare策略产生，尚未证明。不改学校时钟，不部署未经证实的curl切换，不关闭TLS或无限重试403。

当前已连接R2的一次只读元数据查询返回401/Unauthorized后停止；不能因此断言原始备份不存在。需要完成以下任一项才能继续Yang恢复：

1. **学校／Figshare网络支持**：核实下列公开入口的403，或提供学校批准且可访问这些源的数据传输节点；
2. **恢复既有备份读取权限**：修复已连接R2的读取授权，再从真实对象清单定位冻结v5原始或压缩成员。密钥不得发聊天或提交Git。

可复制给学校网络／HPC管理员的说明：

> 用户zhuziyuan在login1恢复CC BY 4.0公开科研数据（DOI:10.25452/figshare.plus.22671172.v5，文件ID51001884）。Python与系统curl的HTTPS GET Range请求均在Figshare入口返回403 HTML，无重定向；GitHub API及其它数据源可用。请核实出站／代理策略与服务端拒绝，或提供允许大文件下载的数据传输节点。所需公开入口为`https://ndownloader.figshare.com/files/51001884`与`https://api.figshare.com/v2/file/download/51001884`；官方正常流程随后跳转至`s3-eu-west-1.amazonaws.com`的精确冻结对象`/ptemp-plus-8475456492/51001884/WBCIC_SHUMotorImagerydataset.zip`，需要HTTPS GET及Range支持。无需SSH密码、GitHub token或任何签名URL。原始数据约68.04GB，按已选ZIP成员传输约43.98GB；登录端仅作下载，解压、EEG预处理和训练留在计算节点。

### 同字节备份如何接续现有任务

仅使用已实际列出的对象映射。312个原生成员恢复至现有`raw/yang`的相同相对路径后，现有`verified_existing()`会按大小、306项冻结SHA及全部CRC初次核验并生成**本机**stat回执。`acquire_yang_transport()`发现全部成员完整后直接跳过Figshare；`publish_yang_offline()`沿用原清单生成原生manifest，无需重写训练框架或改hash。不可复制旧机器stat冒充新验收，也不可将NPZ、其它Yang版本或不同档案冒充同字节输入。

如备份是压缩成员，还需要真实local ZIP header与transport清单；不能只凭压缩长度生成验证回执。可先下载到独立staging，待当前传输释放原锁后再发布到同一cache，避免两个进程同时写。现有Dreyer下载、BNCI缓存、项目身份、原失败与训练资源配置保持；后台不因一字节探测通过就开始训练。

## 诊断实现与既有证据（保留，不要求重跑）

用户提供的2026-10-24 13:30 UTC学校输出确认：GitHub Contents写入及回读通过；18份BNCI缓存复用通过；Dreyer首对象一字节GET Range通过；Yang首个GET Range仍403，尚未获得`yang_route_verified`。这不能证明403来自Figshare入口、S3存储或中间网络，也不能证明全部数据已完成。现有下载器会继续其它独立数据集，全部载荷齐备前不提交新的GPU训练。

两个官方入口在开发环境再次实测为302→206和302→302→206，均只读取同一冻结ZIP的1字节；两入口经过同一下载服务及S3后端。实测官方签名约10秒有效；一次有界过期对照得到标准`AccessDenied`过期错误，现有处理器能正确识别。学校本次403的具体原因仍未观察到，不能把该对照当成学校故障结论，也不能将所有403改为无限重试。

`DIAGNOSE_YANG_ON_SCHOOL.py`独立执行两条官方入口的一次GET Range定位，使用当前已安装代码的相同TLS、代理和精确对象跳转规则。它只输出：

- 每跳公开hostname、入口/存储阶段及HTTP状态；
- Content-Type类别、Location是否存在、受控响应日期及Age；
- 本机时钟判断的签名过期布尔，S3错误Code白名单及标准过期错误布尔；
- 成功时只读1字节，S3错误体最多读取8192字节并仅提取上述受控字段。

URL query、签名、完整Location、错误正文均不输出。不关闭TLS、不跟随未知主机、不自动重试403、不读取ZIP目录或EEG，不安装依赖、不操作Slurm、不重启下载器、不写现有cache或任务记录。请保留正在运行的Dreyer下载。该工具不构成源验收或训练授权。

在login1运行（交付消息提供固定commit的一行下载命令）：

```bash
/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python -B -u /tmp/paper1-yang-diagnose.py
```

默认复用`/public/home/zhuziyuan/projects/PAPER1_HPC_20261023`中的标准库下载代码；其它安装目录可通过`--code`指定。该命令不读取GitHub token，也不需要新凭据。默认返回0表示诊断报告已生成；是否可访问须看每条路线的实际状态及`range_probe_verified`，不能将退出0视为数据或训练完成。当前学校输出已取得，不要求重复诊断。

相关验证：`tests/test_yang_route_diagnostic.py`8项测试，以及`evidence/yang_route_diagnostic_live_20261024.json`中的开发环境真实单字节探测。学校补件结果见本文件顶部，不能用开发环境成功替代学校拒绝。科学输入、模型、种子、hash和统计计划未改；作业资源继续为`hpc_gpu`、单作业单节点、2GPU、总24CPU及128G。
