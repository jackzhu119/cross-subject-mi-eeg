# Yang学校GET403：最小定位入口

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

默认复用`/public/home/zhuziyuan/projects/PAPER1_HPC_20261023`中的标准库下载代码；其它安装目录可通过`--code`指定。只需把输出的安全JSON贴回以确定后续修订。该命令不读取GitHub token，也不需要新凭据。默认返回0表示诊断报告已生成；是否可访问须看每条路线的实际状态及`range_probe_verified`，不能将退出0视为数据或训练完成。

相关验证：`tests/test_yang_route_diagnostic.py`8项测试，以及`evidence/yang_route_diagnostic_live_20261024.json`中的开发环境真实单字节探测。学校端结果尚未取得。科学输入、模型、种子、hash和统计计划未改；作业资源继续为`hpc_gpu`、单作业单节点、2GPU、总24CPU及128G。
