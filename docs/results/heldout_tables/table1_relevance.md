Relevance against the rule label (Fuster rules on the human features, primary) and the human label. Binary: relevant = high or moderate. Values: estimate [95 % bootstrap interval over records].

| Approach | Input | n | Binary F1 (rule) | Binary P (rule) | Binary R (rule) | Four-class agreement (rule) | Binary F1 (human) | Four-class agreement (human) |
|---|---|---|---|---|---|---|---|---|
| 1. Rules on extracted features | Short text (abstract / repository description) | 42 | 0.65 [0.49, 0.79] | 0.59 [0.41, 0.78] | 0.73 [0.54, 0.90] | 0.31 [0.19, 0.45] | 0.57 [0.36, 0.74] | 0.21 [0.10, 0.36] |
| 1. Rules on extracted features | Long text (PDF text) | 19 | 0.86 [0.67, 0.97] | 0.80 [0.57, 1.00] | 0.92 [0.75, 1.00] | 0.42 [0.21, 0.63] | 0.55 [0.25, 0.78] | 0.26 [0.11, 0.47] |
| 1. Rules on extracted features | Long text (native PDF) | 19 | 0.86 [0.69, 0.97] | 0.80 [0.57, 1.00] | 0.92 [0.75, 1.00] | 0.47 [0.21, 0.68] | 0.64 [0.33, 0.83] | 0.32 [0.11, 0.53] |
| 2b. Combined (features + category) | Short text (abstract / repository description) | 42 | 0.78 [0.64, 0.89] | 0.66 [0.48, 0.81] | 0.95 [0.85, 1.00] | 0.40 [0.26, 0.55] | 0.64 [0.45, 0.78] | 0.36 [0.21, 0.50] |
| 2b. Combined (features + category) | Long text (PDF text) | 19 | 0.85 [0.67, 0.97] | 0.85 [0.62, 1.00] | 0.85 [0.62, 1.00] | 0.58 [0.37, 0.79] | 0.70 [0.40, 0.90] | 0.42 [0.21, 0.63] |
| 2. Scoring only | Short text (abstract / repository description) | 42 | 0.70 [0.51, 0.83] | 0.67 [0.47, 0.85] | 0.73 [0.52, 0.90] | 0.45 [0.31, 0.60] | 0.56 [0.34, 0.73] | 0.40 [0.26, 0.55] |
| 2. Scoring only | Long text (PDF text) | 19 | 0.86 [0.67, 0.97] | 0.80 [0.57, 1.00] | 0.92 [0.75, 1.00] | 0.63 [0.42, 0.84] | 0.55 [0.25, 0.78] | 0.37 [0.16, 0.58] |
