Feature extraction, precision / recall / F1 [95 % interval of F1]. Yes/no fields scored as flags (not stated = false). Class fields: H/M/L classes of the relevance rules.

| Field | r1 features abstract | r1 features pdf text | r1 features pdf native | r2 combined abstract | r2 combined pdf text | r1 features sections |
|---|---|---|---|---|---|---|
| *n records (failed)* | 68 (0) | 31 (0) | 31 (0) | 68 (0) | 31 (0) | 31 (0) |
| **EBV features** | | | | | | |
| data_type | 0.18 / 0.31 / 0.23 [0.14, 0.31] | 0.18 / 0.44 / 0.26 [0.14, 0.37] | 0.21 / 0.52 / 0.30 [0.18, 0.40] | 0.21 / 0.33 / 0.26 [0.17, 0.34] | 0.23 / 0.48 / 0.31 [0.19, 0.43] | 0.21 / 0.36 / 0.26 [0.14, 0.38] |
| geospatial_info_dataset | 0.10 / 0.28 / 0.14 [0.06, 0.24] | 0.09 / 0.44 / 0.14 [0.04, 0.28] | 0.09 / 0.56 / 0.15 [0.03, 0.26] | 0.10 / 0.28 / 0.15 [0.06, 0.24] | 0.08 / 0.44 / 0.13 [0.03, 0.25] | 0.06 / 0.33 / 0.11 [0.00, 0.22] |
| species | 0.26 / 0.59 / 0.36 [0.22, 0.55] | 0.23 / 0.72 / 0.35 [0.20, 0.55] | 0.23 / 0.74 / 0.35 [0.20, 0.55] | 0.24 / 0.59 / 0.34 [0.21, 0.54] | 0.25 / 0.72 / 0.38 [0.21, 0.60] | 0.38 / 0.76 / 0.50 [0.33, 0.69] |
| temp_range_i | 0.47 / 0.30 / 0.37 [0.19, 0.52] | 0.50 / 0.93 / 0.65 [0.46, 0.81] | 0.52 / 1.00 / 0.68 [0.50, 0.82] | 0.47 / 0.30 / 0.37 [0.19, 0.52] | 0.56 / 1.00 / 0.71 [0.53, 0.85] | 0.50 / 0.93 / 0.65 [0.46, 0.80] |
| temp_range_f | 0.40 / 0.27 / 0.32 [0.14, 0.48] | 0.39 / 0.73 / 0.51 [0.28, 0.70] | 0.41 / 0.80 / 0.55 [0.33, 0.71] | 0.42 / 0.27 / 0.33 [0.14, 0.48] | 0.44 / 0.80 / 0.57 [0.34, 0.74] | 0.43 / 0.80 / 0.56 [0.35, 0.72] |
| temporal_range_class | 0.53 / 0.33 / 0.41 [0.22, 0.57] | 0.50 / 0.93 / 0.65 [0.46, 0.81] | 0.48 / 0.93 / 0.64 [0.45, 0.79] | 0.53 / 0.33 / 0.41 [0.22, 0.57] | 0.52 / 0.93 / 0.67 [0.47, 0.82] | 0.50 / 0.93 / 0.65 [0.46, 0.80] |
| spatial_range_km2 | 0.02 / 0.03 / 0.02 [0.00, 0.08] | 0.19 / 0.36 / 0.25 [0.08, 0.45] | 0.23 / 0.36 / 0.28 [0.09, 0.50] | 0.02 / 0.03 / 0.02 [0.00, 0.07] | 0.23 / 0.43 / 0.30 [0.12, 0.50] | 0.19 / 0.36 / 0.24 [0.07, 0.44] |
| spatial_range_class | 0.36 / 0.67 / 0.47 [0.33, 0.60] | 0.46 / 0.86 / 0.60 [0.39, 0.77] | 0.59 / 0.93 / 0.72 [0.55, 0.87] | 0.37 / 0.70 / 0.48 [0.34, 0.61] | 0.50 / 0.93 / 0.65 [0.46, 0.82] | 0.41 / 0.79 / 0.54 [0.33, 0.72] |
| time_series | 0.17 / 1.00 / 0.29 [0.00, 0.67] | 0.00 / n/a / 0.00 [0.00, 0.00] | 0.00 / n/a / 0.00 [0.00, 0.00] | 0.14 / 1.00 / 0.25 [0.00, 0.67] | 0.00 / n/a / 0.00 [0.00, 0.00] | 0.00 / n/a / 0.00 [0.00, 0.00] |
| **Modulators** | | | | | | |
| multispecies | 0.28 / 1.00 / 0.43 [0.24, 0.59] | 0.24 / 1.00 / 0.38 [0.11, 0.61] | 0.24 / 1.00 / 0.38 [0.11, 0.61] | 0.27 / 1.00 / 0.42 [0.24, 0.58] | 0.24 / 1.00 / 0.38 [0.11, 0.61] | 0.24 / 1.00 / 0.38 [0.11, 0.62] |
| threatened_species | 0.00 / n/a / 0.00 [0.00, 0.00] | 0.00 / n/a / 0.00 [0.00, 0.00] | 0.00 / n/a / 0.00 [0.00, 0.00] | 0.00 / n/a / 0.00 [0.00, 0.00] | n/a | 0.00 / n/a / 0.00 [0.00, 0.00] |
| new_species_science | n/a | n/a | n/a | n/a | n/a | n/a |
| new_species_region | 0.00 / n/a / 0.00 [0.00, 0.00] | 0.00 / n/a / 0.00 [0.00, 0.00] | 0.00 / n/a / 0.00 [0.00, 0.00] | 0.00 / n/a / 0.00 [0.00, 0.00] | 0.00 / n/a / 0.00 [0.00, 0.00] | n/a |
| bias_north_south | 0.50 / 0.75 / 0.60 [0.27, 0.81] | 0.36 / 1.00 / 0.53 [0.15, 0.79] | 0.29 / 1.00 / 0.44 [0.11, 0.70] | 0.50 / 0.88 / 0.64 [0.35, 0.85] | 0.33 / 1.00 / 0.50 [0.13, 0.75] | 0.17 / 0.50 / 0.25 [0.00, 0.50] |
| **All fields** | | | | | | |
| micro average | 0.21 / 0.41 / 0.28 [0.23, 0.35] | 0.23 / 0.65 / 0.34 [0.25, 0.43] | 0.24 / 0.70 / 0.35 [0.26, 0.44] | 0.21 / 0.42 / 0.28 [0.23, 0.35] | 0.26 / 0.68 / 0.37 [0.27, 0.47] | 0.27 / 0.64 / 0.38 [0.29, 0.46] |

**Taxa at several ranks (GBIF resolution)**

| Condition | Rank | P | R | F1 |
|---|---|---|---|---|
| r1 features abstract | exact | 0.59 | 0.74 | 0.66 |
| r1 features abstract | species | 0.62 | 0.76 | 0.69 |
| r1 features abstract | genus | 0.63 | 0.78 | 0.70 |
| r1 features abstract | family | 0.72 | 0.81 | 0.76 |
| r1 features abstract | broad_group | 0.77 | 0.84 | 0.80 |
| r1 features abstract | group_mentioned | 0.53 | 0.75 | 0.62 |
| r1 features abstract | count_present | 0.60 | 0.18 | 0.27 |
| r1 features abstract | string_exact | 0.09 | 0.21 | 0.13 |
| r1 features abstract | string_fuzzy | 0.26 | 0.59 | 0.36 |
| r1 features pdf text | exact | 0.35 | 0.80 | 0.49 |
| r1 features pdf text | species | 0.39 | 0.80 | 0.52 |
| r1 features pdf text | genus | 0.40 | 0.90 | 0.55 |
| r1 features pdf text | family | 0.43 | 0.93 | 0.59 |
| r1 features pdf text | broad_group | 0.68 | 0.90 | 0.78 |
| r1 features pdf text | group_mentioned | 0.33 | 0.90 | 0.49 |
| r1 features pdf text | count_present | 0.33 | 0.14 | 0.20 |
| r1 features pdf text | string_exact | 0.08 | 0.24 | 0.12 |
| r1 features pdf text | string_fuzzy | 0.23 | 0.72 | 0.35 |
| r1 features pdf native | exact | 0.39 | 0.83 | 0.53 |
| r1 features pdf native | species | 0.44 | 0.83 | 0.57 |
| r1 features pdf native | genus | 0.45 | 0.94 | 0.61 |
| r1 features pdf native | family | 0.50 | 0.93 | 0.65 |
| r1 features pdf native | broad_group | 0.67 | 0.94 | 0.78 |
| r1 features pdf native | group_mentioned | 0.46 | 1.00 | 0.62 |
| r1 features pdf native | count_present | 0.60 | 0.43 | 0.50 |
| r1 features pdf native | string_exact | 0.07 | 0.24 | 0.11 |
| r1 features pdf native | string_fuzzy | 0.23 | 0.74 | 0.35 |
| r2 combined abstract | exact | 0.52 | 0.74 | 0.61 |
| r2 combined abstract | species | 0.54 | 0.76 | 0.63 |
| r2 combined abstract | genus | 0.57 | 0.78 | 0.66 |
| r2 combined abstract | family | 0.69 | 0.81 | 0.74 |
| r2 combined abstract | broad_group | 0.77 | 0.87 | 0.82 |
| r2 combined abstract | group_mentioned | 0.62 | 0.85 | 0.72 |
| r2 combined abstract | count_present | 0.60 | 0.18 | 0.27 |
| r2 combined abstract | string_exact | 0.08 | 0.20 | 0.12 |
| r2 combined abstract | string_fuzzy | 0.24 | 0.59 | 0.34 |
| r2 combined pdf text | exact | 0.38 | 0.80 | 0.51 |
| r2 combined pdf text | species | 0.44 | 0.80 | 0.57 |
| r2 combined pdf text | genus | 0.44 | 0.90 | 0.59 |
| r2 combined pdf text | family | 0.48 | 0.93 | 0.63 |
| r2 combined pdf text | broad_group | 0.76 | 0.90 | 0.82 |
| r2 combined pdf text | group_mentioned | 0.62 | 0.90 | 0.74 |
| r2 combined pdf text | count_present | 0.50 | 0.29 | 0.36 |
| r2 combined pdf text | string_exact | 0.09 | 0.26 | 0.14 |
| r2 combined pdf text | string_fuzzy | 0.25 | 0.72 | 0.38 |
| r1 features sections | exact | 0.51 | 0.94 | 0.66 |
| r1 features sections | species | 0.57 | 0.94 | 0.71 |
| r1 features sections | genus | 0.54 | 0.94 | 0.68 |
| r1 features sections | family | 0.60 | 0.93 | 0.73 |
| r1 features sections | broad_group | 0.82 | 0.87 | 0.84 |
| r1 features sections | group_mentioned | 0.60 | 0.80 | 0.69 |
| r1 features sections | count_present | 0.60 | 0.43 | 0.50 |
| r1 features sections | string_exact | 0.19 | 0.39 | 0.26 |
| r1 features sections | string_fuzzy | 0.38 | 0.76 | 0.50 |
