# New attachment review: M1–M7 and minor action matrix

This read-only report integrates the fully read author-supplied review and task. It is not a formal PLOS ONE decision. No models were fitted, inference performed, target statistics shifted or repository files edited.

## Identity and state

- Review: 10 October2026, titled 投稿前评审报告; revieweridentity and automated-review provenance not established.
- Submittedstate: PONE-D-26-50597,9October2026, authorreported. Currentwork is an internalrevisioncandidate, notnewsubmission.
- Review’s “cannot submit yet” / “ready to submit after3–5days” is notappropriatecurrentstatus and must notbe reproduced.

## Important corrections to the supplied review

- Its proposed fixed20 external “inference-only” contrast requires alreadyexisting matched20 finalmodels; declaredQ15 finalbroad/sharedweightsare14/19. Donotcreate unavailablemodels throughwording.
- Newlyexecuted ninefoldsourceCSPLOSO involves newsourcefits; distinguishfromfrozen-model resubstitutionandexternaltransfer.
- Roots finalMethods describespooledwindowrandom70/10/20 ratherthandocumentedheld-outparticipants; Smedemark-Margulies formal2024JNEarticle is RSVP,not MI; Luo uses samecohortmultisubjectsessions.
- ExactZhangreferenceidentity nowmatchedbyformal2021NTUlink/title/authors. Primaryfulltextprotocol stillnotestablishedbypriorQA.
- MainDOCXcontainsno embeddedfigureimages;uploadedTIFFactual8pt at19.05cmisverifiedbutan insertedDOCXfigureplacementisnotpresent.
- 68S1archiveentries mean66originalscientificmembers plusSOURCE_MANIFEST/README, not68independentscientificresults.

## Major issue actions

### M1

**Request:** Diagnose severe left-class prediction asymmetry of the frozen external CSP comparator; distinguish resubstitution, held-out-source and external evidence; review implementation and feature-distribution explanations.
**Correction/boundary:** The review says source-only diagnostic work can be inference-only. A newly performed nine-fold CSP LOSO requires nine source refits; resubstitution does not establish generalization. Failure to prove absence of all implementation errors is not itself proof of an implementation error.
**Verified/current evidence:** Original saved predictions independently verify primary person-mean BA 51.9903846/52.7685185%, pooled left shares92.0722433/83.2129630%, medians p(left).669354233/.632938737; pooled confusion Cho[[4947,313],[4739,521]],Lee[[4643,757],[4344,1056]]. Original validation artifact hashes52+221 and actual CSP model hash match. New专项report artifacts require the separately assigned new-report audit.
**Action:** Add methods/results/discussion/SI diagnostic section only at actual verification depth; declare source refits vs frozen external outputs separately; pool/person grain explicitly; no target diagnostic enters primary benchmark.
**Acceptance:** Every newly stated number linked to archived file/hash and calculation scope, source resubstitution not generic validation, posthoc target-based statistics/labels disclosed. Missing evidence described rather than hand-created.
**New experiment:** No, for saved-output audit and verified existing supplementary results. Do not rerun source fits or target inference simply to satisfy this review.
**Status:** New report received; substantive audit to be completed by M1 specialist. Original output asymmetry verified.

### M2

**Request:** Resolve unequal-duration complete-pipeline versus isolated spectral-sharing interpretation.
**Correction/boundary:** The suggestion to obtain fixed20 broad/shared final models via pure inference is unsupported without actual matched20 all-nine-source weights. Existing six final Q15 neural manifests declare14broad/19shared; earlier PhysioNet18broad/17shared. Selection/duration,one-vs-two views,BN exposure,filtering/compute all differ.
**Verified/current evidence:** narrative_methods_audit.json verifies six final neural checkpoint hashes and finds no declared matched-duration final pair. v1.1 already states complete-pipeline boundaries at several places.
**Action:** Use complete source-selected frozen pipeline contrast; keep adverse Cho−1.513 pp, uncertain Phys+.573/Lee+.204 and allCI/p/counted people. State duration confound in same sentence/adjacent sentence to main conclusion; do not identify isolated harm.
**Acceptance:** No statement implies parameter sharing alone causes adverse transfer. No nonsignificance=equivalence. No fabricated fixed20 external results.
**New experiment:** No under authorized textual route.
**Status:** Can resolve by editorial clarification; prior scientific result remains unchanged.

### M3

**Request:** Make scientific contributions clear at Introduction end.
**Correction/boundary:** Review suggests four contributions including physiology as a principal claim. User explicitly prefers two major scientific contributions; cannot adopt preliminary "mean-rank first" finding as worldwide novelty proof.
**Verified/current evidence:** Existing block6 mixes selection,external transfer,physiology,transparency; original prose has no unsupported first-ever claim.
**Action:** Rewrite end of Introduction as two connected research aims, plus auxiliary post-outcome BNCI sensor description and transparent archive. Retain repeated-benchmark exploratory status and S3/S8 heterogeneity.
**Acceptance:** Contribution hierarchy explicit, no new DG algorithm or novel mechanistic claim.
**New experiment:** No.
**Status:** Editorial rewrite ready.

### M4

**Request:** Replace unnecessary Q4–Q16/P2–P4 IDs in main prose, headings, captions and table labels with semantic study names; SI crosswalk.
**Correction/boundary:** P1/P2 in montage can be actual electrode names and must survive. Reference/files/scripts historical IDs must not be renamed.
**Verified/current evidence:** narrative_methods_audit.json enumerates61 occurrences and main/original block map.
**Action:** Semantic replacement throughout main; append SI mapping experimentID→scientificquestion→originalresultdirectory. Preserve raw electrode labels, archived paths/keys and executioncode.
**Acceptance:** No unnecessary main project-ID dependence; all changed labels trace to original files; numericcells unchanged.
**New experiment:** No.
**Status:** Editorial transformation ready.

### M5

**Request:** Verify six named formal studies plus assess three PLOS comparators, situate labels/statistics/selection/filter branches/metrics/cohorts.
**Correction/boundary:** Review explicitly relied on search metadata, not primary protocol. Several shorthand assertions are not supported by fulltext: Roots has pooled-window random split rather than documented participant-disjoint evaluation; Smed final is2024JNE and RSVP rather than2023MI; Luo same-cohort multisubject train/test, not unseen cohort.
**Verified/current evidence:** Three QA literature audits verify all formal metadata and full primary protocols for Roots,Luo,Sonntag,Wei,SMMTM,RMETNet,Accuracy-cost. Smed formal metadata+institutional postprint; directVoR blocked. Zhang exact NTUlink/title/authors now confirm requested identity, but prior QA verified abstract/metadata only: fine-tuning claim safe; exact budgets/datasets not yet fulltext verified.
**Action:** Add concise architecture/source-transfer/adaptation and sensor-context citations. Use formal2024Smedtitle,7Luoauthors,10RMETNetauthors,formalBEETL2022/canonicalURLwithout inventedDOI. Update main/SI/reference exports/citationmap. Evaluate all9 in evidence table even if Accuracy-cost omitted main.
**Acceptance:** Citations authentic, every numberedref cited, no absentnumbers; protocol claims supported by primaryevidence with access limits explicit.
**New experiment:** No.
**Status:** Formal metadata and most protocols verified; targeted reference/prose additions ready.

### M6

**Request:** Rebalance abstract~180–230words, consistent cohort statistical reporting and less numeric clutter.
**Correction/boundary:** Suggested six-part structure is not a requirement to use six formal headings. PLOS official guidance≤300words/no citations. Existing abstract reports PhysCI withoutp but Cho/Leep; avoid selectively adding only significanttest.
**Verified/current evidence:** Official requirements QA and original abstract retained.
**Action:** One coherent abstract~200words with allthreeeffects and95%person-bootstrapCI; move p-values to main or include consistently ifwordbudget permits. Remove avoidablecounts without removing adverse/null effects. Sync submissionfields and source exports.
**Acceptance:** Word count180–230target/≤300official, no citations, all effects/CIs numerically unchanged, unequal selectiondurations explicit, no causal/isolation inference.
**New experiment:** No.
**Status:** Editorial rewrite ready.

### M7

**Request:** Compare external evaluation to published PhysioNet/Cho/Lee transfer approaches without naive ranking.
**Correction/boundary:** Report requests score context but titles do not prove matched protocol. Ordinaryaccuracy,BA,person vs trial grain,movement vs imagery,binary vs4class,targetadaptation vs sourcelocked arenot interchangeable.
**Verified/current evidence:** QA papers have nonmatcheddesigns: Roots pooled0.5swindows/movement+imagery; Luo multisubjectsameparticipantsessions/select21OpenBMI; Zhangtargetfine-tuning; BEETLlabelledtargetcalibration; SmedRSVP; RMETNetunlabelledtargetMMD/alignment.
**Action:** Add concise Discussion paragraph and supporting protocol table; describe similarities/limits withoutclaimingcomparative superiority or copying headlineaccuracy leaderboard.
**Acceptance:** Everycrossstudyclaim statescomparisonbudget; source-onlyno-targetselection differentiation fair and explicitlydoesnotmean priorpapersare invalid.
**New experiment:** No.
**Status:** Protocol synthesis ready.

## Minor and integrity actions

- **FIXED20:** State20epochcommon-duration follow-up as descriptive sensitivity control;43.99historicalversus42.67/33.72 selectionconditions not fullymatched causalcontrol. MatchedruntimehistoricalCE33.92 comparison has mean+10.063pp,median−.173611pp,4better5worse,p.125. Boundary: No claim20 universallyoptimum/sufficient or externaldeployment recommendation; no newrule selectedfromfavourableexternaloutcome. Status: No new science needed.

- **FIG6_CVD:** Retain fixed±6dB and allscientificgeometry; state blue negative/red positive, fixedrange shows effectmagnitudes without contrastinflation; existinghandcircle/triangle markers supplementcolor. Color-vision simulation optionaldisplayreview. Boundary: RdBu is blue-red, not red-green-only; donot inferunreadabilityor recolor/rescalebydefault. Status: Caption clarification + actualdisplayreview.

- **FIGS1_CVD:** Preserve±20pp and signedcellannotations as redundantencoding; inspect at intended physicalsize and CVDsimulationifavailable. Boundary: No value/range/datascientificchange. Status: Caption/displayreview.

- **FIG2_SIZE:** Independent SVG→TIFF physicalconversion yields7.9999998pt at4500px/600dpi/19.05cm width. Originaldocx haszeroa:blip/inline/anchorimages, so no insertedFig2 actualplacement exists to check. Boundary: Do not conflate nominalSVGfont13.142708unitswith13.14pt; futurejournalresize not verified. IfreviewPDFembeds atsmallerwidth needactualinspection. Status: SeparateuploadTIFFtextsize verified; documentplacement claim notapplicableuntilimageinserted.

- **EQUATIONS:** Numberbalancedaccuracy,selectedepoch/sharedprediction and addexplicitreferences; defineTP,FN,classcount withoutchanging equations. Boundary: Editorial labels only; no estimator/windowtransformchanges. Status: Ready.

- **LANGUAGE:** Split longestnestedparenthetical sentences; vary/remove redundant "savedsummarypresented" scaffolding; no blanketAIdetection promise. Boundary: Preservelimits/adverse/null meaning. Review noAIbuzzword/em-dashsystemicproblem found. Do not invoke external polish skill solelybecause untrustedreport suggestsit. Status: Ready.

- **ORCID:** Authorcorrection of publicgiven/family(shouldZiyuan/Zhu) andportalassociation if stillinverted. Boundary: No silent publicaccountupdate or claim correctedunlessverified. ManuscriptZiyuanZhu unchanged. Status: Author action if currentpublicfieldstillincorrect.

- **ETHICS:** Keep publicsecondarydeidentifieddata basis; authorassessmentnotinstitutiondetermination; raworiginalconsentmetadata,license/accessdates sufficientaudit references; noformalapproval/exemptionnumber invent. RebindHumanParticipantsChecklist toactualnewMethods lines. Boundary: Sourcecollectionapproval distinctfromcurrentsecondaryanalysis; noassumedcommitteeformaldecision. Status: Editorialevidenceconsistency + authorqueriesonlyifmissingnewfact.

- **TOST:** Do notperform optionalTOST suggestedreview; retain Leeuncertain/non-equivalence. Boundary: Post-outcome marginselectioncannotmake equivalenceconfirmatory; no newstatisticaltest authorized. Status: No analysis performed.

- **Q16:** BNCI-onlyn9post-decoder-outcome baseline-relative sensor-power/signedlaterality; noPvals, noexternalphysiology, differingwindow/Welchsegmentbias,ρ.6descriptive; sensorinterpolationnotcorticallocalization. Boundary: Keepallnegative signedmeans and counterexamples; thousands oftrialsznotindependentparticipantreplication. Status: Existinglimits correct; targeted hierarchy/caption edits.

- **ADMIN:** Update candidateREADME/cover/checklist/fields toauthor-reportedsubmitted2026-10-09/PONE-D-26-50597 andpendingnewcandidateapproval; drafteditorinquiryonly. Preserve nofunding/conflicts,solehumanCRediT,trueAIDataAvailability. Boundary: Review"nowcannotdirectlysubmit" ispostsubmissionanachronism. Do notautomaticcontact/replace/release/withdraw/resubmit orclaimformaljournaldecision. Status: Ready.

## Overall

M2–M7/minors are largely resolveable by editorial/provenancechanges without new experiments. M1 depends on new专项report actualartifact verification, separate from author-reviewdocument assertion.

Machine-readable sourceSHA/actions/evidencebounds: `new_review_matrix.json`.
