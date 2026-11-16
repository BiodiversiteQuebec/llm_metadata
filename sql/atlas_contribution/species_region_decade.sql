-- Per-species Atlas coverage by region x decade. GIT-IGNORED OUTPUT.
--
-- Per-species extracts stay out of the public repository (data-sharing
-- policy). Write the result under artifacts/atlas/ (ignored by git):
--   q.py -f sql/atlas_contribution/species_region_decade.sql --csv artifacts/atlas/species_region_decade.csv
--
-- Same filters as group_region_decade.sql: administrative regions and the
-- north / south of the 49th parallel, sensitive taxa excluded.
-- One row per valid species (id_taxa_ref_species) x region x decade, with the
-- taxonomy needed to match dataset taxa at genus, family or group rank.
WITH grp AS (
    SELECT DISTINCT ON (gl.id_taxa_obs) gl.id_taxa_obs, g.short
    FROM rubus.taxa_obs_group_lookup gl
    JOIN rubus.taxa_groups g ON g.id = gl.id_group AND g.level = 1
    ORDER BY gl.id_taxa_obs, g.id
)
SELECT
    oc.type AS region_type,
    r.name AS region_name,
    oc.id_taxa_ref_species,
    min(t.species) AS species,
    min(t.genus) AS genus,
    min(t.family) AS family,
    min(t."order") AS taxon_order,
    min(t.class) AS taxon_class,
    min(t.phylum) AS phylum,
    min(t.kingdom) AS kingdom,
    min(CASE
        WHEN t.class = 'Insecta' THEN 'INSECTS'
        WHEN grp.short = 'ARTHROPODS' THEN 'OTHER_ARTHROPODS'
        ELSE coalesce(grp.short, 'UNGROUPED')
    END) AS taxon_group,
    CASE
        WHEN oc.year_obs IS NULL THEN 'unknown'
        WHEN oc.year_obs < 1950 THEN 'before_1950'
        ELSE ((oc.year_obs / 10) * 10)::text || 's'
    END AS period,
    sum(oc.count_obs) AS n_observations,
    count(DISTINCT oc.id_datasets) AS n_datasets
FROM atlas_api.obs_counts oc
JOIN public.regions r ON r.fid = oc.fid
JOIN api.taxa t ON t.id_taxa_obs = oc.id_taxa_obs
LEFT JOIN grp ON grp.id_taxa_obs = oc.id_taxa_obs
WHERE ((oc.type = 'admin' AND oc.scale = 2) OR oc.type = 'admin_nord_sud')
  AND NOT coalesce(t.sensitive, false)
  AND oc.id_taxa_ref_species IS NOT NULL
GROUP BY oc.type, r.name, oc.id_taxa_ref_species, 12
ORDER BY 1, 2, 3, 12
