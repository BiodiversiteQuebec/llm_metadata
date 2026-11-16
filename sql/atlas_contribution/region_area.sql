SELECT type AS region_type, name AS region_name, round(sum(area_km2)::numeric) AS area_km2 FROM public.regions WHERE (type='admin' AND scale=2) OR type='admin_nord_sud' GROUP BY 1,2 ORDER BY 1,2
