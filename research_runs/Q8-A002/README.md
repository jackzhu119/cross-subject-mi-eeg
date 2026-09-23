# Q8-A002

Inner-fold influence audit.

No model training.

This analysis tests how strongly each pair of source-validation
subjects influences the selected training duration.

For every Q5/Q6 LOSO fold:

1. use the original four validation folds;
2. remove one validation fold;
3. recompute mean validation CE over the remaining three;
4. select the earliest global minimum;
5. measure the selected-epoch shift.

This analysis must not be used to decide to exclude a validation
subject pair based on target performance.
