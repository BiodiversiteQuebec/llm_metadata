Feature extraction, precision / recall / F1 [95 % interval of F1]. Yes/no fields scored as flags (not stated = false). Class fields: H/M/L classes of the relevance rules.

| Field | r1 features abstract | r1 features pdf text | r1 features pdf native | r2 combined abstract | r2 combined pdf text |
|---|---|---|---|---|---|
| *n records (failed)* | 30 (0) | 16 (0) | 16 (0) | 30 (0) | 16 (0) |
| **EBV features** | | | | | |
| data_type | 0.38 / 0.50 / 0.43 [0.28, 0.57] | 0.33 / 0.56 / 0.42 [0.24, 0.60] | 0.26 / 0.50 / 0.34 [0.19, 0.51] | 0.42 / 0.50 / 0.46 [0.33, 0.59] | 0.31 / 0.50 / 0.38 [0.19, 0.59] |
| geospatial_info_dataset | 0.18 / 0.43 / 0.26 [0.09, 0.43] | 0.16 / 0.62 / 0.25 [0.10, 0.41] | 0.14 / 0.62 / 0.22 [0.09, 0.38] | 0.24 / 0.57 / 0.33 [0.16, 0.50] | 0.13 / 0.50 / 0.21 [0.05, 0.39] |
| species | 0.40 / 0.62 / 0.48 [0.30, 0.72] | 0.53 / 0.70 / 0.60 [0.35, 0.95] | 0.30 / 0.67 / 0.41 [0.23, 0.76] | 0.31 / 0.56 / 0.40 [0.24, 0.60] | 0.45 / 0.70 / 0.55 [0.32, 0.87] |
| temp_range_i | 0.86 / 0.57 / 0.69 [0.48, 0.85] | 0.73 / 0.85 / 0.79 [0.58, 0.97] | 0.79 / 0.85 / 0.81 [0.62, 0.97] | 0.93 / 0.62 / 0.74 [0.55, 0.88] | 0.67 / 0.77 / 0.71 [0.47, 0.92] |
| temp_range_f | 0.79 / 0.52 / 0.63 [0.40, 0.81] | 0.53 / 0.62 / 0.57 [0.32, 0.80] | 0.60 / 0.69 / 0.64 [0.38, 0.87] | 0.79 / 0.52 / 0.63 [0.40, 0.81] | 0.53 / 0.62 / 0.57 [0.32, 0.80] |
| temporal_range_class | 0.86 / 0.57 / 0.69 [0.48, 0.85] | 0.73 / 0.85 / 0.79 [0.58, 0.97] | 0.86 / 0.92 / 0.89 [0.75, 1.00] | 0.93 / 0.62 / 0.74 [0.55, 0.88] | 0.73 / 0.85 / 0.79 [0.58, 0.97] |
| spatial_range_km2 | 0.04 / 0.05 / 0.04 [0.00, 0.13] | 0.57 / 0.73 / 0.64 [0.38, 0.86] | 0.47 / 0.64 / 0.54 [0.30, 0.77] | 0.04 / 0.05 / 0.04 [0.00, 0.13] | 0.47 / 0.64 / 0.54 [0.30, 0.79] |
| spatial_range_class | 0.46 / 0.60 / 0.52 [0.31, 0.71] | 0.64 / 0.82 / 0.72 [0.48, 0.90] | 0.60 / 0.82 / 0.69 [0.45, 0.87] | 0.50 / 0.70 / 0.58 [0.38, 0.75] | 0.60 / 0.82 / 0.69 [0.45, 0.87] |
| time_series | 0.60 / 0.60 / 0.60 [0.00, 0.89] | 0.40 / 0.67 / 0.50 [0.00, 0.86] | 0.75 / 1.00 / 0.86 [0.40, 1.00] | 0.75 / 0.60 / 0.67 [0.00, 1.00] | 0.40 / 0.67 / 0.50 [0.00, 0.86] |
| **Modulators** | | | | | |
| multispecies | 0.56 / 1.00 / 0.72 [0.47, 0.89] | 0.50 / 1.00 / 0.67 [0.00, 1.00] | 0.43 / 1.00 / 0.60 [0.00, 0.91] | 0.56 / 1.00 / 0.72 [0.47, 0.89] | 0.50 / 1.00 / 0.67 [0.00, 1.00] |
| threatened_species | 1.00 / 0.80 / 0.89 [0.67, 1.00] | 0.83 / 0.83 / 0.83 [0.50, 1.00] | 1.00 / 0.67 / 0.80 [0.40, 1.00] | 1.00 / 0.90 / 0.95 [0.80, 1.00] | 0.83 / 0.83 / 0.83 [0.50, 1.00] |
| new_species_science | n/a | n/a | n/a | n/a | n/a |
| new_species_region | 0.33 / 1.00 / 0.50 [0.00, 1.00] | n/a | n/a | 0.33 / 1.00 / 0.50 [0.00, 1.00] | n/a |
| bias_north_south | 1.00 / 0.60 / 0.75 [0.40, 0.95] | 0.88 / 1.00 / 0.93 [0.74, 1.00] | 0.64 / 1.00 / 0.78 [0.50, 0.95] | 1.00 / 0.70 / 0.82 [0.55, 1.00] | 0.64 / 1.00 / 0.78 [0.50, 0.95] |
| **All fields** | | | | | |
| micro average | 0.42 / 0.54 / 0.47 [0.40, 0.54] | 0.47 / 0.72 / 0.57 [0.46, 0.67] | 0.37 / 0.70 / 0.49 [0.37, 0.60] | 0.41 / 0.55 / 0.47 [0.39, 0.54] | 0.43 / 0.68 / 0.52 [0.42, 0.61] |

**Taxa at several ranks (GBIF resolution)**

| Condition | Rank | P | R | F1 |
|---|---|---|---|---|
| r1 features abstract | exact | 0.78 | 0.81 | 0.80 |
| r1 features abstract | species | 0.94 | 0.91 | 0.93 |
| r1 features abstract | genus | 0.88 | 0.94 | 0.91 |
| r1 features abstract | family | 0.76 | 0.96 | 0.85 |
| r1 features abstract | broad_group | 0.97 | 0.89 | 0.93 |
| r1 features abstract | group_mentioned | 1.00 | 0.79 | 0.88 |
| r1 features abstract | count_present | 1.00 | 0.22 | 0.36 |
| r1 features abstract | string_exact | 0.05 | 0.08 | 0.06 |
| r1 features abstract | string_fuzzy | 0.40 | 0.61 | 0.48 |
| r1 features pdf text | exact | 0.82 | 0.78 | 0.80 |
| r1 features pdf text | species | 0.94 | 1.00 | 0.97 |
| r1 features pdf text | genus | 0.85 | 1.00 | 0.92 |
| r1 features pdf text | family | 0.82 | 1.00 | 0.90 |
| r1 features pdf text | broad_group | 0.95 | 0.95 | 0.95 |
| r1 features pdf text | group_mentioned | 1.00 | 0.86 | 0.92 |
| r1 features pdf text | count_present | 1.00 | 1.00 | 1.00 |
| r1 features pdf text | string_exact | 0.14 | 0.18 | 0.16 |
| r1 features pdf text | string_fuzzy | 0.53 | 0.70 | 0.60 |
| r1 features pdf native | exact | 0.48 | 0.78 | 0.60 |
| r1 features pdf native | species | 0.61 | 1.00 | 0.76 |
| r1 features pdf native | genus | 0.65 | 1.00 | 0.79 |
| r1 features pdf native | family | 0.61 | 1.00 | 0.76 |
| r1 features pdf native | broad_group | 0.87 | 0.95 | 0.91 |
| r1 features pdf native | group_mentioned | 1.00 | 0.86 | 0.92 |
| r1 features pdf native | count_present | 1.00 | 0.33 | 0.50 |
| r1 features pdf native | string_exact | 0.13 | 0.30 | 0.18 |
| r1 features pdf native | string_fuzzy | 0.29 | 0.67 | 0.41 |
| r2 combined abstract | exact | 0.63 | 0.81 | 0.71 |
| r2 combined abstract | species | 0.76 | 0.89 | 0.82 |
| r2 combined abstract | genus | 0.76 | 0.90 | 0.82 |
| r2 combined abstract | family | 0.66 | 0.96 | 0.78 |
| r2 combined abstract | broad_group | 0.86 | 0.91 | 0.89 |
| r2 combined abstract | group_mentioned | 1.00 | 0.86 | 0.92 |
| r2 combined abstract | count_present | 1.00 | 0.11 | 0.20 |
| r2 combined abstract | string_exact | 0.18 | 0.33 | 0.23 |
| r2 combined abstract | string_fuzzy | 0.31 | 0.56 | 0.40 |
| r2 combined pdf text | exact | 0.70 | 0.78 | 0.74 |
| r2 combined pdf text | species | 0.81 | 1.00 | 0.90 |
| r2 combined pdf text | genus | 0.74 | 1.00 | 0.85 |
| r2 combined pdf text | family | 0.70 | 1.00 | 0.82 |
| r2 combined pdf text | broad_group | 0.90 | 0.95 | 0.92 |
| r2 combined pdf text | group_mentioned | 1.00 | 0.86 | 0.92 |
| r2 combined pdf text | count_present | 1.00 | 1.00 | 1.00 |
| r2 combined pdf text | string_exact | 0.21 | 0.33 | 0.26 |
| r2 combined pdf text | string_fuzzy | 0.45 | 0.70 | 0.55 |
