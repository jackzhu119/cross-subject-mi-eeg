# 将已核验的本地版本发布到main

本会话已完成文档与本地Git提交，但GitHub写入工具要求审批，当前策略为never；终端外网代理也不可达。因此不能声称远端已更新。

交付的 `paper1-review2-20261018.bundle` 只携带本轮提交及其新增对象，以原main提交 `7b2932124ca06d8bcd65c9e618cd7ce65d68796f` 为前提。下载bundle后，在你已有GitHub推送权限且联网正常的仓库目录运行以下命令。把路径替换成实际下载路径；不需要修改API或云服务器凭据。

```bash
git fetch origin main
git bundle verify /path/to/paper1-review2-20261018.bundle
git fetch /path/to/paper1-review2-20261018.bundle refs/heads/paper/p1-plos-review2-20261018:refs/remotes/paper1-local/review2
git merge-base --is-ancestor origin/main refs/remotes/paper1-local/review2 && git push origin refs/remotes/paper1-local/review2:main
```

最后一步只接受保持远端历史的快进更新。如果远端已经出现不兼容的新提交，祖先检查或push会拒绝；保留现场再合并，不强推、不reset、不删除既有科学结果。

推送后可验证：

```bash
git ls-remote origin refs/heads/main
git rev-parse refs/remotes/paper1-local/review2
```

两行中的提交SHA应一致。GitHub发布与向PLOS门户换稿是两件事；本包未执行正式投稿、换稿或联系编辑。
