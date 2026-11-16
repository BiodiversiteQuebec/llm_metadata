# Atlas contribution scores from extraction vs annotation

Run `20261115_225438_atlas_abstract_dev.json` (claude-haiku-5-5, abstract), 30 records (non-held-out). Spearman rank correlation [95 % bootstrap interval], over records where both sides have the score.

| Score | Extraction vs annotation | n | Defined from extraction | Defined from annotation |
|---|---|---|---|---|
| taxonomic | 0.63 [0.54, 1.00] | 12 | 16 | 12 |
| spatial | 0.52 [0.25, 0.82] | 30 | 30 | 30 |
| temporal | 0.56 [-0.05, 0.99] | 13 | 14 | 21 |
| group_gap | 0.98 [0.94, 1.00] | 30 | 30 | 30 |
| n_gaps | 0.49 [0.22, 0.73] | 30 | 30 | 30 |

**Extracted scores vs the Fuster rule label:**

```
{
  "n": 30,
  "spearman_ci": {
    "taxonomic": [
      0.31524416249564025,
      -0.11355197392120114,
      0.7484811885651197,
      16
    ],
    "spatial": [
      0.3533283532004191,
      0.04943859376322253,
      0.5952123320504048,
      30
    ],
    "temporal": [
      0.3044108830178277,
      -0.12971020804997443,
      0.6897722703148749,
      14
    ],
    "group_gap": [
      0.062135316382186126,
      -0.3153703446282111,
      0.4097501958771979,
      30
    ],
    "n_gaps": [
      0.336110427442733,
      0.03731030606003918,
      0.5758289219624358,
      30
    ]
  }
}
n_gaps     0    1    2   All
fuster                      
H        7.0  3.0  0.0  10.0
M       11.0  0.0  1.0  12.0
L        8.0  0.0  0.0   8.0
X        NaN  NaN  NaN   NaN
All     26.0  3.0  1.0  30.0
```

Kinds of record: {'traits_or_genetics': 13, 'abundance': 11, 'environmental_or_other': 2, 'occurrence': 2, 'presence_absence': 2}

Occurrence records available: {None: 15, False: 11, True: 4}

Place match levels: {'province': 27, 'region': 15, 'north_south': 12, 'outside': 9, 'unmatched': 5}
