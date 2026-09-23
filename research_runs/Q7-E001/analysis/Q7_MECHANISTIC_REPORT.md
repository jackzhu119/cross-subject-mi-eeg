# Q7-E001 Mechanistic Ablation Report

## Four-cell design

| Cell | Normalization | Epochs | Source |
|---|---|---:|---|
| A | OFF | 2 | Q5-E001 |
| B | ON | 2 | Q7-E001 |
| C | OFF | 16 | Q7-E001 |
| D | ON | 16 | Q6-E001 |

## Mean results over three seeds

| Cell | BA | Macro-F1 | Kappa | Entropy | Dominant share |
|---|---:|---:|---:|---:|---:|
| A | 0.2610 | 0.1254 | 0.0147 | 0.1304 | 0.9416 |
| B | 0.2569 | 0.1172 | 0.0093 | 0.0827 | 0.9751 |
| C | 0.6771 | 0.6715 | 0.5694 | 0.9561 | 0.3669 |
| D | 0.6586 | 0.6502 | 0.5448 | 0.9037 | 0.4387 |

## Mechanistic contrasts

- A_raw_2: **0.2610**
- B_norm_2: **0.2569**
- C_raw_16: **0.6771**
- D_norm_16: **0.6586**
- normalization_effect_at_2_epochs_B_minus_A: **-0.0041**
- training_duration_effect_without_norm_C_minus_A: **+0.4161**
- training_duration_effect_with_norm_D_minus_B: **+0.4016**
- normalization_effect_at_16_epochs_D_minus_C: **-0.0185**
- factorial_interaction_D_minus_C_minus_B_plus_A: **-0.0145**

## Interpretation boundary

This is a mechanistic experiment centered on S3. It is not evidence that the same mechanism generalizes to the population of unseen subjects.

The four-cell pattern should be interpreted before designing Q8. No additional Q7 variants should be added after inspecting these results.
