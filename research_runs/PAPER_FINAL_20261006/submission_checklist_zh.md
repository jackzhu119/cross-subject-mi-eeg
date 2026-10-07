# 投稿前完成清单 — 7 October 2026 版本

作者与通讯作者已填写为朱子元（Ziyuan Zhu），邮箱 zzy2630816871@gmail.com，单位英文为 College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China。该英文形式有发表论文单位用法支持，尚不能冒充校方官网英文命名确认。Q15 最终科学结果、Q16 BNCI 生理分析及当前论文交付各有独立证据；当前版本应以自己的结果、验证和发布回执为准。

## 科学内容与分析边界

- [ ] 零校准明确限定为不拟合目标参数、不用目标结果选择模型。说明目标标签可用于元数据、资格判断、计分及隔离的生理描述。
- [ ] Q15 原始 source fits=15，迁移新增 source fits=0，target fits=0。Q16 和本文制作新增 decoder fits=0、checkpoint inference=0；生理功率计算不算训练。
- [ ] Q14 与 Q15 保留不同冻结、源模型、窗口及统计流程。Q14 两神经网络选择 18/17 epochs，Q15 为 14/19 epochs；其比较是完整流程比较。
- [ ] Q5/Q6 人群平均差同时包含 normalization 与选定时长变化；S3 为 2→16 epochs、S5 为 13→12。Q7 的固定时长对照提供单人分离诊断，不能将其扩为普遍结论。
- [ ] Cho 52 人/10,520 试次，Lee 54 人/10,800 试次，只用两次会话的 `EEG_MI_train`。PhysioNet 109 人/4,918 试次另列，不合并为统一准确率或一个独立检验。
- [ ] Cho shared−broad=−1.513 pp，95% 区间 [−2.249,−0.804]，两队列 Holm p≈0.000100。Lee +0.204 pp，区间 [−0.515,+0.969]，p≈0.604。不显著不等于等效，负结果不掩盖。
- [ ] Q16 以实际 `run_manifest.json` 和独立验证记录确认结果；protocol/metadata/freeze 不能单独证明完成。范围为 BNCI 九人两会话、18 文件、108 runs、5,184 四分类试次；手别分析 2,592 试次，保留原 artifact flags。
- [ ] Q16 保持固定 baseline [−1.5,−0.5) s/task [0.5,2.5) s、native 250 Hz/22 EEG，不加 CAR/滤波/decoder transforms。dB 比值估计及不等 Welch 段数偏差可见。
- [ ] C3/C4 laterality 附绝对通道值；负的侧化差不自动代表绝对 ERD。生理与 BA 关联 n=9、六个描述性相关无 p 值，不作为机制证明，不反向调整模型。
- [ ] Q16 BNCI 组件不等于外部 Cho/Lee 生理方案完成。模板传感器图不等于个体电极测量或皮层定位；常数增益不变性不能修复采集参考、提示时序或物理标定。

## AUTHOR ACTION REQUIRED — 必须由作者确认的信息

| 项目 | 作者需完成的操作 | 文件 |
|---|---|---|
| 作者与隶属 | 核对唯一作者、通讯作者、学院英文署名、ORCID、通讯地址与实际贡献 | `author_information_template.md` |
| 目标期刊 | 优先考虑 JNE 的学科适配；若冲刺 TNSRE，评估创新门槛与风险；核验投稿当天的 JCR 及本单位口径 | `journal_strategy_zh.md` |
| 伦理与原数据同意 | 作者已确认本次二次分析无需伦理审批或豁免；原始采集伦理与同意以来源文献为准 | `author_information_template.md` |
| 资助/利益冲突/致谢 | 作者已确认无资助、无利益冲突；致谢如有仍须核对许可 | `author_information_template.md` |
| 人工科学审校 | 审读正文、图表、补充、负结果与推断边界，承担最终稿责任 | 主稿和 supplement |
| 使用与发表权利 | 分别核对数据条款与仓库 LICENSE，保留官方原始数据入口 | `reproducibility_readme.md` |
| AI 披露 | 如实记录 Codex 用于分析代码、资料核对、起草及图表材料的范围；按期刊要求写工具/模型信息 | 作者模板 |
| 原创/重叠/独家投稿 | 确认相关稿件、预印本及独家投稿；这些声明尚未代填 | 两份未发送投稿信 |

## 技术交付核对

- [ ] 保存预测复算、Q16 独立 periodogram/聚合/关联核验与当前图表逐项一致；查看验证记录的实际覆盖范围。
- [ ] 当前 PDF、Word、Markdown、TeX 的正文与引用一致；PDF 是 ReportLab 导出，原生 TeX 编译按实际回执表述。
- [ ] 工作流程图没有目标计分/生理到模型学习的反馈箭头；传感器坐标、颜色范围、截断记录、单位与图注一致。
- [ ] 正文与补充拆分后的图表编号、交叉引用、术语、模型预算、参考文献及通讯信息完整。
- [ ] 当前哈希清单、ZIP 与 GitHub 读回回执匹配；5 October 的发布确认只证明旧版。
- [ ] 若期刊要求双盲，另生成匿名文件；当前实名版本不能称为匿名。
- [ ] DOI 归档只在真实创建、元数据和许可确认后填写；本次没有 journal submission 或 archive DOI。

当前材料提供作者可审阅的投稿稿件基础。自然语言质量应来自准确叙述、具体证据与人工修改；如实披露实际辅助范围，不承诺规避 AI 检测。

## 本次文字与发布复核

- [ ] 标题使用 fixed spectral-sharing pipelines；外部比较不暗示 parameter-sharing 的单因素因果。
- [ ] Figure 1 使用 baseline-relative μ/β power，并区分 eligibility/mapping metadata、scoring-only ground truth 和 no target fitting/selection。
- [ ] 主文说明 source validation 为 2/2/2/3 人四组、等 fold 权重；未重新评估 grouping sensitivity。
- [ ] 新增两篇直接相关的 2025 DG 原始论文，保留其信息预算和选择流程的核查边界，不作 SOTA 对比。
- [ ] 28 条引用连续、全部被引用；EEGPT 按官方会议页和 PDF 保留 Guagnyu Wang。
- [ ] **AUTHOR TO CONFIRM MODEL/VERSION** 与本人实际审阅范围见 `ai_disclosure_submission_draft.md`。
- [ ] 发布前执行 `release_plan.md`：冻结文件保护、当前数字和文档检查、包校验、GitHub 逐文件读回，均通过后才更新首页/归档；DOI 未创建时不填写。
