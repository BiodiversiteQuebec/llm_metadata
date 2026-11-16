# Atlas contribution scores from extraction vs annotation

Run `20261115_225748_heldout_atlas_abstract.json` (claude-haiku-5-5, abstract), 68 records (dev + held-out allowed). Spearman rank correlation [95 % bootstrap interval], over records where both sides have the score.

| Score | Extraction vs annotation | n | Defined from extraction | Defined from annotation |
|---|---|---|---|---|
| taxonomic | 0.51 [-0.03, 0.89] | 42 | 56 | 43 |
| spatial | 0.48 [0.09, 0.82] | 34 | 58 | 35 |
| temporal | 0.94 [0.65, 1.00] | 10 | 17 | 30 |
| group_gap | 1.00 [0.99, 1.00] | 60 | 65 | 61 |
| n_gaps | 0.49 [0.22, 0.74] | 60 | 65 | 61 |

**Extracted scores vs the Fuster rule label:**

```
{
  "n": 42,
  "spearman_ci": {
    "taxonomic": [
      -0.034673143946575745,
      -0.36651398458156026,
      0.27583685905500066,
      38
    ],
    "spatial": [
      0.3626095727176035,
      0.08160740031029357,
      0.6063677288707532,
      37
    ],
    "temporal": [
      0.16526684880256934,
      -0.641725563526596,
      0.7938469888336047,
      10
    ],
    "group_gap": [
      0.024876213522390184,
      -0.2640801859380138,
      0.31195059326761276,
      41
    ],
    "n_gaps": [
      0.24727227279354674,
      -0.04532310161194417,
      0.5144528495122813,
      41
    ]
  }
}
n_gaps  0.0  1.0  2.0  All
fuster                    
H         8    3    1   12
M         6    4    0   10
L        11    1    0   12
X         6    1    0    7
All      31    9    1   41
```

Kinds of record: {'traits_or_genetics': 25, 'abundance': 17, 'presence_absence': 12, 'environmental_or_other': 8, 'occurrence': 6}

Occurrence records available: {False: 33, None: 28, True: 7}

Place match levels: {'province': 46, 'outside': 32, 'north_south': 30, 'region': 18, 'unmatched': 8, 'unknown': 3}
