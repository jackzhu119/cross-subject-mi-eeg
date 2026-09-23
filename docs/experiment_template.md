# Experiment Protocol Template

## 1. Research Question

## 2. Hypothesis

## 3. Dataset

- Dataset/version:
- Subjects:
- Sessions/runs:
- Classes:
- Inclusion/exclusion:

## 4. Preprocessing

- Channel types and channel selection:
- Sampling rate / resampling:
- Filter settings:
- Epoch window and time reference:
- Artifact policy:
- Normalization and where it is fitted:

## 5. Method

- Features:
- Model:
- Hyperparameters:
- Random seed(s):

## 6. Train/Test Strategy

- Unit of split: trial / session / subject
- Outer evaluation:
- Inner model selection:
- Leakage checks:

## 7. Evaluation Metrics

- Primary metric:
- Secondary metrics:
- Subject-level aggregation:

## 8. Results

只填写真实运行并保存了原始输出的结果。

## 9. Interpretation

## 10. Limitations

## 11. Next Step

## Artifact checklist

- [ ] Frozen config
- [ ] Environment/package versions
- [ ] Split manifest
- [ ] Per-trial predictions
- [ ] Per-subject metrics
- [ ] Aggregate metrics
- [ ] Figures
- [ ] Runtime log and warnings
- [ ] Failed attempts retained or explicitly referenced

