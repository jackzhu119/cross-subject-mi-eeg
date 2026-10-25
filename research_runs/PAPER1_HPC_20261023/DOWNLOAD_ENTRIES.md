# 直接下载到学校服务器：官方入口与完整清单

**R2不是数据下载、科学校验或训练的必要条件。** 用户可在允许联网下载的学校节点直接把数据保存到`/public/home/zhuziyuan/projects/paper1-risk-v1/raw`。现有代码已支持续传、完整文件复用、校验后自动接续；无需先下载到个人电脑或本云环境。

## 数据入口

| 数据 | 固定对象数／原生大小 | 官方入口 | 已取得的学校证据 |
|---|---|---|---|
| BNCI2014_001 | 18／779873919字节 | [TU Graz官方文件目录](https://lampx.tugraz.at/~bci/database/001-2014/)；备用为原BNCI入口，逐文件URL见TSV | 18份已完成并校验；保留缓存 |
| Yang v5 | 312个选中成员／68044344823字节 | [原作者v5发布页](https://plus.figshare.com/articles/dataset/Brain_Computer_Interface_Motor_Imagery-EEG_Dataset/22671172/5)；[官方文件入口](https://ndownloader.figshare.com/files/51001884)；[官方API下载入口](https://api.figshare.com/v2/file/download/51001884) | 学校Python和curl均在入口403；尚无可用学校下载路线证明 |
| Dreyer原始EDF | 174／2515343396字节 | [NEMAR固定版本](https://data.nemar.org/nm000250/v1.0.5/)；174个逐文件URL见TSV | 首文件GET Range路线通过，已有部分文件完成；不代表174份全通过 |

Yang原始完整ZIP为65630556299字节，发布MD5为`e5384a58ac51b0d0c78a28a500185479`。现有代码只下载选中的43981251776字节压缩成员，并在计算节点离线解压后核验原生文件；这不等于已计算完整ZIP的MD5。两个官方文件入口经过同一下载服务及存储后端，不是独立镜像。

## 可直接下载的清单

- [download_entries.tsv](download_entries.tsv)：504行固定输入，每行含相对路径、大小、原SHA/CRC、入口及官方备用入口；原字段值来自现有冻结清单。
- [SHA256SUMS.expected](SHA256SUMS.expected)：498项原生SHA，包括18 BNCI、306 Yang信号/event及174 Dreyer。另6项Yang元数据原契约只有CRC，保留TSV中的原CRC，不伪造冻结SHA。

`transport=zip_member_not_individual_http_url`表示ZIP内部成员，不是312个独立下载链接；不要把重复的ZIP入口当作312份整包下载。`zip_header_offset`是原ZIP成员头偏移，实际数据偏移还须解析原local header；现有下载器负责处理，无需手工计算。

在login1下载清单（交付消息给出固定commit链接）：

```bash
curl -4 -f --connect-timeout 8 --max-time 60 --retry 1 -H 'Accept: application/vnd.github.raw+json' 'https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg/contents/research_runs/PAPER1_HPC_20261023/download_entries.tsv?ref=main' -o /public/home/zhuziyuan/projects/paper1-risk-v1/download_entries.tsv
```

这条只保存清单，不重新提交作业，不修改已有数据或凭据。查看实际下载日志使用：

```bash
tail -n 30 /public/home/zhuziyuan/projects/paper1-risk-v1/logs/login-pipeline.log
```

已配置项目的原一行启动／续跑入口仍是`bash ~/projects/PAPER1_HPC_20261023/LAUNCH.sh --gpus 2 --memory 128G`；它识别现有任务并复用文件，不另建科学项目。但是，整理URL或重跑入口不能使学校已经返回403的Yang路线自动可用。此403解除前不能宣称全部载荷完成或开始新训练，不建议重复运行同一403测试。

## 不经R2的合法传输路线

1. 学校提供可访问原作者Figshare文件的、获准下载大文件的数据传输节点，直接写上述共享目录；下载器无需改科学配置。
2. 从另一台允许访问官方源的机器下载原始文件，通过学校已有授权传输入口送入该目录；保留原字节，校方新机器首次按原大小/SHA/CRC验证，再复用。不能假设SSH已可达，也无需把密码或私钥发到聊天。

已查询NEMAR `nm000348`的v1.0.1–v1.0.5公开清单：v1.0.1缺少所需306份原生文件；v1.0.2–v1.0.5的306份大小相同，但冻结SHA匹配均为0。因此这些副本尚不能替代现有严格输入。来源为[官方NEMAR发布页](https://nemar.org/dataset/nm000348?v=v1.0.5)，元数据比对记录在`evidence/yang_nemar_historical_comparison_20261025.json`。不以更换数据版本或修改冻结SHA来“修复”下载。

所有原数据仍保存到学校本地。GPU资源继续为`hpc_gpu`、一个作业一个节点、2GPU、总24CPU及128G；新增入口清单不改变模型、时长、种子、统计计划、原失败或旧论文。
