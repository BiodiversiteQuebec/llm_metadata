Relevance against the rule label (Fuster rules on the human features, primary) and the human label. Binary: relevant = high or moderate. Values: estimate [95 % bootstrap interval over records].

| Approach | Input | n | Binary F1 (rule) | Binary P (rule) | Binary R (rule) | Four-class agreement (rule) | Binary F1 (human) | Four-class agreement (human) |
|---|---|---|---|---|---|---|---|---|
| 1. Rules on extracted features | Short text (abstract / repository description) | 30 | 0.80 [0.65, 0.91] | 0.78 [0.61, 0.95] | 0.82 [0.65, 0.96] | 0.47 [0.30, 0.63] | 0.73 [0.55, 0.86] | 0.37 [0.20, 0.53] |
| 1. Rules on extracted features | Long text (PDF text) | 16 | 0.81 [0.61, 0.93] | 0.73 [0.50, 0.93] | 0.92 [0.73, 1.00] | 0.44 [0.19, 0.69] | 0.77 [0.55, 0.93] | 0.31 [0.12, 0.56] |
| 1. Rules on extracted features | Long text (native PDF) | 16 | 0.81 [0.61, 0.93] | 0.73 [0.50, 0.93] | 0.92 [0.73, 1.00] | 0.38 [0.12, 0.62] | 0.77 [0.55, 0.93] | 0.31 [0.12, 0.56] |
| 2b. Combined (features + category) | Short text (abstract / repository description) | 30 | 0.86 [0.75, 0.95] | 0.76 [0.60, 0.90] | 1.00 [1.00, 1.00] | 0.57 [0.40, 0.73] | 0.77 [0.62, 0.88] | 0.40 [0.23, 0.57] |
| 2b. Combined (features + category) | Long text (PDF text) | 16 | 0.88 [0.72, 1.00] | 0.85 [0.64, 1.00] | 0.92 [0.73, 1.00] | 0.44 [0.19, 0.69] | 0.75 [0.53, 0.91] | 0.19 [0.00, 0.38] |
| 2. Scoring only | Short text (abstract / repository description) | 30 | 0.81 [0.67, 0.91] | 0.76 [0.59, 0.92] | 0.86 [0.71, 1.00] | 0.43 [0.27, 0.63] | 0.65 [0.47, 0.80] | 0.30 [0.17, 0.47] |
| 2. Scoring only | Long text (PDF text) | 16 | 0.77 [0.55, 0.93] | 0.71 [0.47, 0.93] | 0.83 [0.60, 1.00] | 0.38 [0.12, 0.62] | 0.72 [0.48, 0.90] | 0.31 [0.12, 0.56] |
