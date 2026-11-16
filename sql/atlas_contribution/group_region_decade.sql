-- Atlas coverage by broad taxonomic group x region x decade (aggregates only).
--
-- Source: atlas_api.obs_counts (pre-aggregated region x taxon x dataset x year),
-- staging database, read-only. Run with the bq-atlas-db runner (q.py):
--   q.py -f sql/atlas_contribution/group_region_decade.sql --csv docs/atlas_contribution/group_region_decade.csv
--
-- Region levels kept: administrative regions (type admin, scale 2) and the
-- north / south of the 49th parallel split (type admin_nord_sud).
-- Broad group: the Atlas level-1 taxon group (rubus.taxa_groups), with
-- arthropods split into insects (class Insecta) and other arthropods.
-- Sensitive taxa (api.taxa.sensitive: SENSITIVE list or any Quebec legal
-- status) are excluded, so no count can reveal them.
-- Taxa that belong to no level-1 group are reported as UNGROUPED.
WITH grp AS (
    SELECT DISTINCT ON (gl.id_taxa_obs) gl.id_taxa_obs, g.short
    FROM rubus.taxa_obs_group_lookup gl
    JOIN rubus.taxa_groups g ON g.id = gl.id_group AND g.level = 1
    ORDER BY gl.id_taxa_obs, g.id
)
SELECT
    oc.type AS region_type,
    r.name AS region_name,
    CASE
        WHEN t.class = 'Insecta' THEN 'INSECTS'
        WHEN grp.short = 'ARTHROPODS' THEN 'OTHER_ARTHROPODS'
        ELSE coalesce(grp.short, 'UNGROUPED')
    END AS taxon_group,
    CASE
        WHEN oc.year_obs IS NULL THEN 'unknown'
        WHEN oc.year_obs < 1950 THEN 'before_1950'
        ELSE ((oc.year_obs / 10) * 10)::text || 's'
    END AS period,
    sum(oc.count_obs) AS n_observations,
    count(DISTINCT oc.id_taxa_ref_species) AS n_species,
    count(DISTINCT oc.id_datasets) AS n_datasets
FROM atlas_api.obs_counts oc
JOIN public.regions r ON r.fid = oc.fid
JOIN api.taxa t ON t.id_taxa_obs = oc.id_taxa_obs
LEFT JOIN grp ON grp.id_taxa_obs = oc.id_taxa_obs
WHERE ((oc.type = 'admin' AND oc.scale = 2) OR oc.type = 'admin_nord_sud')
  AND NOT coalesce(t.sensitive, false)
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2, 3, 4
