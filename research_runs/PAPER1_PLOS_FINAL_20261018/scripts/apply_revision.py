#!/usr/bin/env python3
"""Rebuild a contribution-led manuscript without changing frozen scientific results."""
from pathlib import Path
import argparse, csv, hashlib, json, re, shutil, zipfile


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,text):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text.rstrip()+'\n',encoding='utf-8')
def section(text, heading, next_heading, body):
    a=text.index(heading)+len(heading);b=text.index(next_heading,a)
    return text[:a]+'\n\n'+body.strip()+'\n\n'+text[b:]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--analysis',type=Path,required=True);ap.add_argument('--spec',type=Path,required=True);args=ap.parse_args()
    src,out,an=args.source,args.out,args.analysis;spec=json.loads(args.spec.read_text());out.mkdir(parents=True,exist_ok=True)
    assert digest(src/'manuscript_en.md')==spec['source_manuscript_sha256']
    for d in ['figure_data','tables']:
        shutil.copytree(src/d,out/d,dirs_exist_ok=True)
    for n in ['S1_Data.zip','S2_Neural_Predictions.csv.gz','S3_CSP_Predictions.csv.gz','REFERENCES.md']:
        shutil.copy2(src/n,out/n)
    for n in ['Data_Availability.md','Ethics_Author_Statement.md','Ethics_AI_and_Author_Boundaries.md','Licensing_and_Provider_Terms.md']:
        (out/'submission').mkdir(exist_ok=True);shutil.copy2(src/'submission'/n,out/'submission'/n)
    for n in ['author_confirmation_20261018.json','ethics_provenance.json','provider_license_metadata.json','reference_verification.json','review2_reference_verification.json']:
        (out/'evidence/source_records').mkdir(parents=True,exist_ok=True);shutil.copy2(src/'evidence'/n,out/'evidence/source_records'/n)
    shutil.copytree(an,out/'evidence/additional_descriptives',dirs_exist_ok=True)
    shutil.copy2(an/'S4_Additional_descriptives.csv',out/'tables/S4_Additional_descriptives.csv')
    shutil.copy2(an/'primary_joint_participant_changes.csv',out/'tables/S4_primary_joint_participant_changes.csv')
    (out/'scripts').mkdir(exist_ok=True)
    shutil.copy2(args.spec,out/'scripts/revision_spec.json')
    shutil.copy2(__file__,out/'scripts/apply_revision.py')
    text=(src/'manuscript_en.md').read_text()
    text=re.sub(r'^Short title: .*$', 'Short title: '+spec['short_title'],text,flags=re.M)
    text=section(text,'## Abstract','## Introduction',spec['abstract'])
    text=section(text,'## Introduction','## Materials and methods',spec['introduction'])
    text=section(text,'## Discussion','## Conclusions',spec['discussion'])
    text=section(text,'## Conclusions','## Data and code availability',spec['conclusions'])
    acc=re.search(r'### Completed evaluation and checkpoint accounting\n\n(.*?)\n\n### Source expansion improved weaker-class coverage',text,re.S)
    accounting=acc.group(1).replace('These counts describe saved evaluations, not independent training replicates.','Participant-paired inference uses the 85 people; checkpoint aliases retain their shared model identity.')
    text=text[:acc.start()]+'### Source expansion improved weaker-class coverage'+text[acc.end():]
    old='Descriptively, 72 participants improved, ten declined and three were unchanged; the median paired increase was 21.6667 points. Fig 3 displays all 85 paired changes.'
    new='Weaker-class recall improved in 72 of 85 participants (84.71%), with a median paired increase of 21.6667 points. Ten participants declined and three were unchanged. An additional post hoc descriptive reconstruction found balanced-accuracy improvement in 71 participants and simultaneous improvement in both endpoints in 66 (77.65%). Fig 3 displays all 85 weaker-class changes; S4 Data supplies the paired joint-improvement inventory.'
    assert old in text;text=text.replace(old,new)
    marker='### Pipeline profiles and descriptive class-recall decomposition'
    text=text.replace(marker,'### Completed evaluation and checkpoint accounting\n\n'+accounting+'\n\n'+marker,1)
    old='The supplementary algebraic decomposition gave a mean absolute class-recall gap of 62.0098 points for S9/BROAD and 31.3824 points for S60/BROAD, a descriptive reduction of 30.6275 points. The reduction follows directly from twice the difference between the corresponding balanced accuracy and weaker-class recall, making the recovery of two-class coverage explicit.'
    new='The mean absolute class-recall gap decreased from 62.0098 points for S9/BROAD to 31.3824 points for S60/BROAD: a reduction of 30.6275 points, or 49.39% relative to the baseline gap. The gap narrowed in 72 of 85 participants, widened in 12 and was unchanged in one. This post hoc descriptive decomposition follows from twice the difference between balanced accuracy and weaker-class recall. Label-specific reconstruction showed right-hand recall rising from 31.01% to 59.64%, accompanied by left-hand recall falling from 85.63% to 68.71%. Thus, the average coverage gain reflects class rebalancing alongside higher balanced accuracy; complete changes for every evaluated configuration are supplied in S4 Data.'
    assert old in text;text=text.replace(old,new)
    old='This decomposition and participant improvement/decline counts are descriptive summaries of the saved predictions.'
    new='This decomposition and participant improvement/decline counts are descriptive summaries of the saved predictions. The present editorial revision additionally reconstructed joint improvement in B and W, participant changes in recall gap, and label-specific recalls from the full saved neural and conventional prediction tables. These post hoc descriptions cover all 34 source-expansion-by-pipeline-by-selector comparisons against S9, retain every direction of change, and introduce no new hypothesis tests. A numerical tie tolerance of 10⁻¹² on the fraction scale defines unchanged observations. The relative gap reduction is 100 × (G(S9)−G(S60))/G(S9), where G is the mean seed-specific absolute recall gap. S4 Data contains the complete descriptive inventory, paired primary changes and calculation script.'
    assert old in text;text=text.replace(old,new)
    replacements={
      'The seed-specific metric is the averaging input in every reported comparison. The inferential unit was the participant, n=85. The inferential sample consists of 85 participant pairs.':'Each inferential comparison used 85 participant pairs after within-participant seed averaging.',
      'Prespecification refers to the archived study configuration, not an external preregistration.':'The archived study configuration defines the prespecified comparisons.',
      'The supplied second-round report also motivated four supplementary post hoc contrasts:':'Four supplementary post hoc contrasts evaluated the following:',
      'A written analysis specification was saved before calculation, after outcomes were already known.':'Their analysis specification was recorded after outcomes were known and before calculation.',
      'These analyses were specified after outcomes were known and supplement the original protocol comparisons.':'These post hoc analyses supplement the original protocol comparisons.',
      'Supplementary post hoc source-expansion comparisons requested during manuscript review.':'Supplementary post hoc source-expansion comparisons.',
      'No scientific experiment was rerun for this manuscript revision.':'The manuscript analysis uses the frozen outputs.',
      'The checks connect recorded input identities, source selections and saved-prediction statistics. Complete numerical sources for the tables and figures accompany the manuscript; S1 Appendix details the scope of each evidence layer.':'The archived checks link input identities, source selections and prediction statistics. Complete numerical sources accompany the tables and figures, with verification scope described in S1 Appendix.',
      'Across the complete selection-rule inventory, seven of eight rules gave positive mean changes for each neural pipeline, expansion and endpoint; tail cross-entropy was the exception. The original S60−S29 and selector contrasts had intervals spanning zero (Table 2); full results remain in S1 Data.':'Across the complete selection-rule inventory, seven of eight rules gave positive mean changes for each neural pipeline, expansion and endpoint. Tail cross-entropy supplied the eight adverse neural endpoint contrasts; full results remain in S1 Data.',
      'The invariant concerns a common trial-wide scale factor.':'',
      'The date, office, basis and dataset coverage were confirmed by the author for this manuscript.':'The author supplied the date, office, basis and dataset coverage of this determination.',
    }
    for old,new in replacements.items():
        assert old in text,old;text=text.replace(old,new)
    for value in ['8.8841×10⁻¹⁷','5.3414×10⁻⁹','1.7805×10⁻⁹','5.5300×10⁻¹⁷','2.6111×10⁻⁹','6.3276×10⁻⁸']:
        text=text.replace('p='+value,'p<0.001').replace('| '+value+' |','| <0.001 |')
    text=text.replace('Unadjusted intervals are not simultaneous confidence intervals.','Intervals are pointwise. Exact p values are retained in S1 Data.')
    ba_paragraph='Balanced accuracy increased from 58.3186% to 64.1716%, a difference of +5.8529 points (95% t CI, 4.1288–7.5771; Holm-adjusted p<0.001). The paired changes show improvement in both average discrimination and coverage of the less-recognized command.'
    assert ba_paragraph in text
    text=text.replace(ba_paragraph+'\n\n','')
    text=text.replace('The paired-bootstrap interval was 17.1468–24.9512 points (Table 2; Fig 2).', 'The paired-bootstrap interval was 17.1468–24.9512 points. '+ba_paragraph+' The complete prespecified comparisons are shown in Table 2; Fig 2.')
    a=text.index('## Figure captions');b=text.index('## Figure-preparation assistance',a)
    capsection=text[a:b]
    caps={int(m[1]):m[2].strip() for m in re.finditer(r'^## Fig (\d)\. (.*?)(?=^## Fig |\Z)',capsection,re.M|re.S)}
    assert set(caps)==set(range(1,8))
    assistance_end=text.index('## References',b)
    assistance=text[b+len('## Figure-preparation assistance'):assistance_end].strip()
    text=text[:a]+text[assistance_end:]
    a=text.index('## Supporting information');b=text.index('## References',a)
    support=text[a:b].strip()+'\n\nS4 Data. Complete additional post hoc descriptive inventory, joint endpoint changes, verification receipt and reproducible calculation script.\n'
    text=text[:a]+text[b:]
    text=text.rstrip()+'\n\n'+support
    needle='The reproducibility README identifies the public numerical evidence, code and separately indexed neural checkpoint archives.'
    text=text.replace(needle,needle+' S4 Data adds the present post hoc descriptive reconstruction without altering the frozen predictions or original hypothesis tests.')
    text=text.replace('and takes responsibility for the final manuscript.','and takes responsibility for the final manuscript. '+assistance)
    text=text.replace('The complete prespecified comparisons are shown in Table 2; Fig 2. Weaker-class recall improved', 'The complete prespecified comparisons are shown in Table 2.\n\nFig 2 displays the complete set of frozen primary and secondary comparisons.\n\nWeaker-class recall improved')
    text=text.replace('Table 3 and Fig 4 show both endpoints', 'Table 3 shows both endpoints')
    text=text.replace('The full source-only epoch inventory is displayed in Fig 5.', 'Fig 4 displays these endpoint profiles and the corresponding class-recall gap.\n\nThe full source-only epoch inventory is displayed in Fig 5.')
    text=text.replace('(Table 4; Fig 6).', '(Table 4).\n\nFig 6 displays the four supplementary paired comparisons.')
    text=text.replace('Balanced accuracy improved in all four configurations (Table 5). All 24', 'Balanced accuracy improved in all four configurations (Table 5).\n\nAll 24')
    text=text.replace('Fig 4C is explicitly identified as a descriptive algebraic decomposition.', 'The class-recall-gap panel is identified as a descriptive algebraic decomposition.')
    for n in range(1,6):
        pat=rf'\*\*Table {n}\..*?\*\*[^\n]*\n\n(?:\|[^\n]*\n)+'
        m=re.search(pat,text,re.S)
        assert m,('table',n)
        block=m[0].strip();text=text[:m.start()]+text[m.end():]
        paras=re.split(r'\n\s*\n',text)
        k=next(i for i,p in enumerate(paras) if re.search(rf'\bTable {n}\b',p))
        paras.insert(k+1,block);text='\n\n'.join(paras)
    for n,cap in caps.items():
        caption=spec['captions'][str(n)]
        paras=re.split(r'\n\s*\n',text)
        k=next(i for i,p in enumerate(paras) if re.search(rf'\bFig {n}\b',p) and not p.startswith('**Fig'))
        insert=k+1
        if insert<len(paras) and paras[insert].startswith('**Table'):
            insert+=1
            if insert<len(paras) and paras[insert].startswith('|'):insert+=1
        paras.insert(insert,caption);text='\n\n'.join(paras)
    text=re.sub(r'\n{3,}','\n\n',text)
    text=text.replace('  Yang', ' Yang').replace('links.  Source', 'links. Source')
    put(out/'manuscript_en.md',text)
    put(out/'submission/Abstract.txt',spec['abstract'])
    put(out/'submission/Cover_Letter.md',spec['cover_letter'])
    supp=(src/'supplementary_en.md').read_text()
    supp+='''\n\n## Additional editorial-stage descriptive reconstruction\n\nThis additional analysis was specified after the original results had been inspected. It introduces no new hypothesis tests and leaves the original primary, three-test secondary and four-test post hoc families unchanged. All 979,200 neural and 61,200 conventional saved trial predictions were read. Each participant/seed contributed 40 labelled trials per class; both classes, all 85 participants and all three seeds were retained. Metrics were computed within seed before averaging seeds within participant. For joint improvement, both the balanced-accuracy and weaker-class-recall paired differences had to exceed 10⁻¹² on the fraction scale.\n\nIn the primary S60−S9 BROAD/tail-recall contrast, 66/85 participants improved on both endpoints, 71 improved in balanced accuracy and 72 improved in weaker-class recall. The mean absolute recall gap declined by 49.39% relative to S9; the gap narrowed in 72 participants, widened in 12 and was unchanged in one. Mean right-hand recall changed from 31.01% to 59.64%, while left-hand recall changed from 85.63% to 68.71%. The larger weaker-class gain is therefore a rebalancing result, not a claim that both fixed physical classes improved.\n\nS4 Data retains all 34 configuration-level comparisons against S9, including adverse and unchanged outcomes, their joint-benefit counts and label-specific changes. It also provides all 85 primary participant changes, the analysis plan, implementation and checksum-bound verification receipt. Every one of the 68 corresponding expansion-by-endpoint means in the previous complete inventory was reproduced within 10⁻¹⁰ percentage points. The source prediction files were unchanged.\n'''
    supp=supp.replace('waiting for editorial permission to replace the submitted version','subject to confirmation of the permitted submission route')
    put(out/'supplementary_en.md',supp)
    fields=(src/'submission/Submission_Fields.md').read_text()
    fields=section(fields,'# PLOS ONE submission fields','## Article and author','Prepared for the 18 October 2026 author-led revision. The earlier submission PONE-D-26-50597 was rejected on 12 October 2026 for duplicate submission. The author acknowledged that decision and requested guidance about a substantially revised future submission on 12 October. Only an automatic acknowledgment was found when correspondence was checked. Editorial permission or instructions for a new submission have not been established. Use these fields after confirming the permitted route; this is not an invited revision.')
    fields=section(fields,'## Prior dissemination and submission route','## Reviewer preferences and publication charge','The manuscript and research materials are publicly accessible on GitHub. The earlier PONE-D-26-50597 submission was rejected on 12 October 2026; it is not currently an in-review manuscript on the evidence inspected. The author has asked whether a substantially revised version may be considered as a new submission. Confirm the editor\'s substantive response and exclusive-consideration status before submitting. Disclose the previous manuscript identifier and decision in the cover letter. The present work package does not constitute editorial permission.')
    fields=fields.replace('Separate `../figures/Fig*.tif` files','Separate `../figures/Fig*.eps` files')
    fields=fields.replace('| S3 Data | `../S3_CSP_Predictions.csv.gz` |','| S3 Data | `../S3_CSP_Predictions.csv.gz` |\n| S4 Data | `../S4_Data.zip` |')
    put(out/'submission/Submission_Fields.md',fields)
    put(out/'submission/Submission_Checklist_zh.md','''# 论文1投稿前检查\n\n稿件和文件格式检查与期刊是否允许再次投稿是两件事。\n\n## 本次已完成\n\n主要阳性发现与创新贡献前置；原预设比较、完整负向结果和参与者变化保留。主文末段集中说明关键适用范围。补充描述分析重算全部保存预测，未重新训练或推理。主文使用连续行号、页码、双倍正文行距和独立标题页；摘要少于300词；图注随首次引用安排，7张EPS单独上传。S1至S4数据文件逐个小于20MB。\n\n## 提交前仍需作者确认\n\n1. 旧稿PONE-D-26-50597已于2026年10月12日被拒，并非在审稿或受邀修回。已查看的询问仅有自动回复，尚未证实编辑允许新投；先取得明确路线说明，并在投稿信披露旧稿。\n2. 确认目前没有同一稿件在其他期刊同时审理，最终审读新主文、图表和门户生成PDF。\n3. 核实伦理免审说明与学校实际决定一致；按期刊需要提供真实支持材料，不填写虚构批准编号。\n4. 核对作者姓名Ziyuan Zhu、单位、邮箱和ORCID 0009-0005-1153-4926，以及门户的资金、利益冲突、数据可用性与AI辅助披露。\n\n本任务仅制作和发布作者稿件，没有登录投稿系统代投，也未获取新的编辑许可。\n''')
    put(out/'README_zh.md','''# 论文1：贡献前置最终作者稿\n\n**Source-cohort expansion improves weaker-class coverage in cross-subject motor-imagery EEG decoding**\n\n本版将已验证的贡献和阳性发现放到摘要、引言、结果与讨论开头：主要弱类召回提高21.17个百分点，平衡准确率提高5.85个百分点；新增完整预测描述分析表明66/85人在两个指标上同时改善，平均类别召回差距缩小49.39%。固定20轮对照与CSP比较提供补充支持。\n\n原来的预设比较与检验家族保持不变；两项未显著的预设比较、tail-CE不利结果、个体下降以及全部标签变化均保留。必要限制集中在讨论最后一段。原冻结结果、代码和先前稿件未覆盖。本目录是作者准备稿，旧稿不是在审状态；再次投稿需先核实编辑许可/路线。\n\n|用途|文件|\n|---|---|\n|主文上传|`main_manuscript.docx`|\n|完整阅读含图|`review_manuscript.pdf`|\n|主文源|`manuscript_en.md`|\n|七张单独投稿图|`figures/Fig*.eps`|\n|详细方法补充|`S1_Appendix.pdf`|\n|原数值和预测|`S1_Data.zip`、`S2_Neural_Predictions.csv.gz`、`S3_CSP_Predictions.csv.gz`|\n|新增联合改善与标签分解|`S4_Data.zip`|\n|修改与合规核对|`REVISION_REPORT_zh.md`、`evidence/validation.json`|\n|投稿信和门户项|`submission/`|\n\n完整包用于下载归档，不能作为一个超过20MB的Supporting Information文件提交；请按表格拆分。\n''')
    put(out/'REPRODUCIBILITY.md','''# Reproducibility of this editorial revision\n\nOriginal manuscript: `cac26b4f818907323863d03e65293efcb5a4b5e2/research_runs/PAPER1_PLOS_REVIEW2_20261018`. Frozen result commit: `040956085499ed788948de0d5a09cddd9eabca56`; executed training code: `0539379578818b3d71f995192e5e8a81cf4d5aef`. The earlier scientific paths are unchanged.\n\nThis revision recomputes metrics from the two saved prediction CSV.GZ files; it does not read raw EEG, deserialize weights, rerun a decoder, or introduce new hypothesis tests. `scripts/analyze_saved_predictions.py` accepts `--source` and `--out`; its complete output is in S4 Data and `evidence/additional_descriptives`. The original 68 aggregate differences and all 85 primary W/BA differences are checked.\n\nThe reusable editorial builder reads `scripts/revision_spec.json`, copies the immutable source package, applies the text revision, re-renders identical figure values, and exports documents. Changes to figure fonts and format do not change their data. EPS uses standard PostScript Times/Symbol fonts; raster previews are for author review. The main document excludes image objects and has continuous line/page numbers.\n\nAll payload checksums are recorded in MANIFEST.sha256. Checkpoint archives remain described by the original public reproducibility evidence; this author package does not redistribute third-party raw recordings or claim new external-cohort confirmation.\n''')
    put(out/'REVISION_REPORT_zh.md','''# 本次改稿与数值复核\n\n## 写作结构\n\n保留原有科学术语与21条参考文献。将结果开头的“运行数量/检查点清单”移到主结果之后；摘要、引言和讨论先讲源队列扩展的实际作用，再讲预算控制、参与者联合收益与跨解码方法支持。删除重复的工作流程否定句，不把source-only、无目标拟合等实验事实当作保守词删除。技术上的目标隔离、事后分析标签、点态区间与参与者统计单位仍在方法中明确，综合限制集中在讨论最后一段。\n\n## 新增而非改写原结果\n\n从全部979,200行神经预测和61,200行CSP预测重算，原68个扩源端点均值差及主比较85人的两指标差值一致。主比较中：66/85人同时提高弱类召回与平衡准确率；71人提高平衡准确率；72人提高弱类召回；72人类别差距缩小。平均类别差距从62.0098降至31.3824个百分点，相对缩小49.39%。这些为新增事后描述，不声称独立新验证，不增加显著性检验。\n\n右手召回提高28.63个百分点伴随左手召回下降16.92个百分点，说明是更平衡的覆盖和平均正确率提高，不能写成“左右手都提高”。两项预设未显著结果、tail-CE负向结果、10人弱类下降保留。S29与CSP阳性比较、固定20轮阳性控制此前已存在，本次主要前置其证据价值，不称新发现。\n\n## 投稿格式\n\n摘要229词；独立标题页、连续行号与页码、双倍正文行距、可编辑表格。图注跟随首次引用，参考文献后列Supporting information。七张图重绘为Times/Symbol标准字体EPS；图数、数值与已核验CSV不变。S1至S4补充文件分别小于20MB。来源链接及核验项目见evidence/plos_requirements.json；实测文件结果见evidence/validation.json。\n\n## 投稿状态更正\n\n旧投稿信的“仍在审”不符合已查看的2026-10-12决定邮件，已更正为此前被拒且询问未来实质修订版路线。自动回复不是重新投稿许可。伦理依据保留作者确认的2026-10-17、重庆医科大学科研处、2023年办法第32(1)条，不编造学校证明或编号。\n''')
    put(out/'evidence/plos_requirements.json',json.dumps({
      'checked_date':'2026-10-18','official_sources':[
        'https://journals.plos.org/plosone/s/submission-guidelines',
        'https://journals.plos.org/plosone/s/figures',
        'https://journals.plos.org/plosone/s/data-availability',
        'https://journals.plos.org/plosone/s/ethical-publishing-practice'],
      'requirements':{'abstract_words_max':300,'full_title_characters_max':250,'short_title_characters_max':100,'editable_main':'DOCX','main_body_spacing':'double','line_numbers':'continuous','page_numbers':True,'figure_formats':['TIFF','EPS'],'figure_bytes_max':10000000,'supporting_file_bytes_max':20000000,'cover_letter_pages_max':1,'figure_caption_placement':'at first in-text citation','supporting_captions':'after references'},
      'submission_route':'Previous rejection verified in correspondence; permission for substantially revised new submission not established. No journal action performed.'},indent=2))
    put(out/'evidence/editorial_source_identity.json',json.dumps({'base_main':spec['base_main'],'source_manuscript_sha256':spec['source_manuscript_sha256'],'raw_saved_predictions_unchanged':all(digest(src/n)==digest(out/n) for n in ['S2_Neural_Predictions.csv.gz','S3_CSP_Predictions.csv.gz']),'new_model_fits':0,'new_decoder_inference':0,'new_hypothesis_tests':0,'scientific_data_preserved':True,'submission_performed':False},indent=2))
    print(json.dumps({'stage':'text_revised','abstract_words':len(spec['abstract'].split()),'main_words':len(text.split()),'tables':5,'figures':7}))
if __name__=='__main__':main()
