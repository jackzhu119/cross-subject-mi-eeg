# Q7 — Normalization × Training-Duration Mechanistic Ablation

## 1. Scientific objective

Q6 produced a large S3 improvement:

- Q5 S3 BA ≈ 0.261
- Q6 S3 BA ≈ 0.659

At the same time:

- Q5 selected 2 epochs
- Q6 selected 16 epochs

Q7 must distinguish between three possible mechanisms:

1. **direct normalization effect**
2. **training-duration / epoch-selection effect**
3. **normalization × training-duration interaction**

Q7 is a mechanistic ablation, not a new hyperparameter search.

---

# 2. Preserve everything that does not need to change

Freeze:

- BNCI2014_001
- same 9 subjects
- same four classes
- same trial identities
- same artifact policy
- same 4–40 Hz filtering
- same 2.5–5.5 s epochs
- same 22 × 750 EEG input
- same EEGNet architecture
- same optimizer
- same learning rate
- same batch size
- same weight decay
- same three final seeds:
  - 20260924
  - 20260925
  - 20260926
- deterministic algorithms
- same held-out target trials
- no target fitting or tuning

Only manipulate:

- normalization on/off
- fixed training duration

---

# 3. Core factorial logic

For each relevant LOSO fold:

| Condition | Normalization | Training epochs |
|---|---|---|
| A | OFF | Q5-selected epoch |
| B | ON | Q5-selected epoch |
| C | OFF | Q6-selected epoch |
| D | ON | Q6-selected epoch |

Interpretation:

A = original Q5-like condition  
D = original Q6-like condition

Therefore A and D should generally be **reused from Q5/Q6**, not retrained unnecessarily.

Only missing cross-conditions B and C need new training.

---

# 4. Critical S3 experiment

For S3:

Q5 epoch = 2  
Q6 epoch = 16

Required four cells:

A. raw / no SourceNorm / 2 epochs  
- already represented by Q5

B. SourceNorm / 2 epochs  
- NEW

C. raw / no SourceNorm / 16 epochs  
- NEW

D. SourceNorm / 16 epochs  
- already represented by Q6

Run the same three seeds for B and C.

This is the primary Q7 mechanistic experiment.

---

# 5. How to interpret S3

### Scenario 1

If:

raw + 16 epochs

approaches Q6 performance,

then much of the S3 gain may be mediated through training duration / source-validation selection.

### Scenario 2

If:

SourceNorm + 2 epochs

already performs strongly,

then normalization has a substantial direct effect independent of longer training.

### Scenario 3

If neither B nor C reproduces D:

SourceNorm + 16 epochs

then the evidence supports an interaction between normalization and training duration.

### Scenario 4

If B and C both improve substantially:

multiple mechanisms may be contributing.

---

# 6. S8 interpretation

S8:

- Q5 selected epoch = 1
- Q6 selected epoch = 1

Therefore Q5 vs Q6 already compares:

raw + 1 epoch

against:

SourceNorm + 1 epoch

Training duration is already matched.

Thus S8 provides existing evidence that normalization itself can induce negative transfer / stronger prediction collapse under the Q5/Q6 protocol.

No duplicated S8 retraining is required merely to recreate this contrast.

Additional S8 training should only be performed if Q7 defines a new mechanistic question in advance.

---

# 7. S5

S5:

- Q5 selected epoch = 13
- Q6 selected epoch = 12

Difference is only one epoch.

Optional cross-conditions can be run if a complete factorial reconstruction is desired:

- SourceNorm + 13
- raw + 12

However S5 is secondary to S3.

Do not allow S5 post-hoc results to redefine the primary Q7 hypothesis.

---

# 8. Other subjects

For:

- S1
- S2
- S4
- S6
- S7
- S8
- S9

Q5 and Q6 selected the same epoch.

Therefore the existing Q5-Q6 comparison already largely isolates normalization at a matched training duration.

Do not waste compute retraining identical conditions without a reproducibility reason.

---

# 9. Primary Q7 outcome

Primary mechanistic outcome for S3:

- balanced accuracy
- macro-F1
- Cohen kappa
- class-wise recall
- prediction entropy
- dominant prediction share

Compare all four factorial cells.

The key question is not simply which condition has the highest BA.

The key question is:

> Which manipulation removes S3's class-collapse failure mode?

---

# 10. Training-dynamics outputs to retain

For every new Q7 fit save:

- epoch
- train loss
- validation loss if applicable
- source-validation CE
- prediction entropy
- class prediction distribution
- final confusion matrix
- logits or probabilities if practical
- selected/fixed training duration
- random seed
- exact scaler receipt
- source subject IDs
- trial IDs
- checkpoint hash

The purpose is to analyze the trajectory leading to collapse or recovery.

---

# 11. Statistical boundary

Q7 is primarily mechanistic.

S3 cannot be treated as population-level proof.

Subject-level population claims still require multiple independent subjects.

Do not perform inferential tests treating seed runs as independent subjects.

Q7 should explain Q6 rather than manufacture a new population-level significance claim.

---

# 12. Q7 experiment identity

Recommended experiment naming:

- `Q7-E001`

Possible subconditions:

- `Q7-E001-B`: SourceNorm + Q5 epoch
- `Q7-E001-C`: Raw + Q6 epoch

Existing references:

- A = Q5-E001
- D = Q6-E001

Avoid duplicating A and D unless an explicit reproducibility rerun is required.

---

# 13. Validation requirements

Q7 validator should verify:

- target subject absent from normalization fitting;
- target subject absent from source-validation selection;
- exact fixed epoch count used;
- exact three seeds;
- identical trial IDs to Q5/Q6;
- identical preprocessing to Q5/Q6;
- only intended factors changed;
- prediction and metric recomputation;
- raw MAT hashes;
- source-code hashes;
- checkpoint hashes.

---

# 14. Stop rule

Do not add new Q7 variants after seeing S3 results.

Predefine the required cross-conditions before training.

After Q7-E001 is run and validated, freeze it before proposing Q8.

---

# 15. Decision after Q7

If normalization has a robust direct effect independent of epoch selection:

- retain SourceNorm as a candidate component.

If the main effect is training dynamics:

- focus later work on optimization / source-only model selection.

If there is an interaction:

- future normalization methods must be evaluated jointly with training dynamics.

If SourceNorm remains highly subject-specific:

- treat it as an explanatory ablation rather than automatically incorporating it into the final method.

---

# 16. Q8 after Q7

Q8 should address the project's original spatial-spectral objective.

Potential direction:

**fixed, source-only spatial-spectral representation + EEGNet/deep model**

Before running Q8:

- specify spectral representation in advance;
- avoid selecting frequency bands using held-out target performance;
- retain strict LOSO;
- preserve Q5/Q6 comparison;
- keep target completely unseen.

Q8 should answer a separate question:

> Can a principled spatial-spectral representation produce broader cross-subject gains than the highly subject-specific Q6 normalization effect?

Exact Q8 implementation should be finalized only after Q7 is interpreted.

---

# 17. Q9

Q9 should only combine components that Q7/Q8 independently justify.

Potential conceptual structure:

source-only normalization  
+ spatial-spectral representation  
+ deep model

But combination must not be assumed beneficial in advance.

A factorial or ablation comparison should determine whether gains are additive or interactive.

---

# 18. External validation

After a final method is fixed:

- identify a compatible independent motor-imagery EEG dataset;
- freeze preprocessing/model choices before external evaluation;
- do not retune using the external target subjects;
- clearly distinguish internal BNCI2014_001 evidence from external generalization evidence.

---

# 19. Immediate next action

When compute/Work access resumes:

1. read Q6 frozen documentation;
2. confirm repository clean state;
3. create an independent Q7 working directory;
4. implement only the two missing S3 cross-conditions:
   - SourceNorm + 2 epochs
   - raw + 16 epochs
5. use three existing final seeds;
6. validate Q7;
7. compare four S3 factorial cells;
8. analyze class-collapse trajectories;
9. freeze Q7 before moving to Q8.

Do not rerun Q5 or Q6.
