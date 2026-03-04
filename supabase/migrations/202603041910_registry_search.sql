-- Search RPC used by edge function `registry-search`

CREATE OR REPLACE FUNCTION public.registry_search(
  q text DEFAULT NULL,
  tags_filter text[] DEFAULT NULL,
  license_filter text DEFAULT NULL,
  match_limit integer DEFAULT 20,
  query_embedding text DEFAULT NULL
)
RETURNS TABLE (
  id text,
  name text,
  description text,
  tags text[],
  license text,
  repo_url text,
  homepage_url text,
  snippet text,
  score double precision
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  has_pg_trgm boolean := EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm');
  has_vector boolean := EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector');
  use_vector boolean := false;
  limit_val integer := GREATEST(1, LEAST(COALESCE(match_limit, 20), 100));
  sql_text text;
BEGIN
  use_vector := has_vector AND query_embedding IS NOT NULL AND length(trim(query_embedding)) > 0;

  IF use_vector THEN
    sql_text := $q$
      SELECT
        r.id,
        r.name,
        r.description,
        r.tags,
        r.license,
        r.repo_url,
        r.homepage_url,
        left(coalesce(r.readme, ''), 400) AS snippet,
        (
          (1 - (r.embedding <=> $5::vector)) * 0.75 +
          CASE
            WHEN $1 IS NULL OR $1 = '' THEN 0
            WHEN $6 THEN GREATEST(similarity(coalesce(r.name, ''), $1), similarity(coalesce(r.description, ''), $1))
            ELSE CASE
              WHEN coalesce(r.name, '') ILIKE ('%' || $1 || '%') OR coalesce(r.description, '') ILIKE ('%' || $1 || '%') THEN 0.15
              ELSE 0
            END
          END
        )::double precision AS score
      FROM public.registry_apps r
      WHERE ($2 IS NULL OR cardinality($2) = 0 OR r.tags && $2)
        AND ($3 IS NULL OR $3 = '' OR r.license = $3)
      ORDER BY score DESC, r.name ASC
      LIMIT $4
    $q$;

    RETURN QUERY EXECUTE sql_text USING q, tags_filter, license_filter, limit_val, query_embedding, has_pg_trgm;
  END IF;

  IF has_pg_trgm THEN
    sql_text := $q$
      SELECT
        r.id,
        r.name,
        r.description,
        r.tags,
        r.license,
        r.repo_url,
        r.homepage_url,
        left(coalesce(r.readme, ''), 400) AS snippet,
        CASE
          WHEN $1 IS NULL OR $1 = '' THEN 0
          ELSE GREATEST(similarity(coalesce(r.name, ''), $1), similarity(coalesce(r.description, ''), $1))
        END::double precision AS score
      FROM public.registry_apps r
      WHERE ($2 IS NULL OR cardinality($2) = 0 OR r.tags && $2)
        AND ($3 IS NULL OR $3 = '' OR r.license = $3)
        AND (
          $1 IS NULL OR $1 = '' OR
          coalesce(r.name, '') % $1 OR
          coalesce(r.description, '') % $1 OR
          coalesce(r.readme, '') ILIKE ('%' || $1 || '%')
        )
      ORDER BY score DESC, r.name ASC
      LIMIT $4
    $q$;

    RETURN QUERY EXECUTE sql_text USING q, tags_filter, license_filter, limit_val;
  END IF;

  sql_text := $q$
    SELECT
      r.id,
      r.name,
      r.description,
      r.tags,
      r.license,
      r.repo_url,
      r.homepage_url,
      left(coalesce(r.readme, ''), 400) AS snippet,
      CASE
        WHEN $1 IS NULL OR $1 = '' THEN 0
        WHEN coalesce(r.name, '') ILIKE ('%' || $1 || '%') THEN 1
        WHEN coalesce(r.description, '') ILIKE ('%' || $1 || '%') THEN 0.75
        WHEN coalesce(r.readme, '') ILIKE ('%' || $1 || '%') THEN 0.5
        ELSE 0
      END::double precision AS score
    FROM public.registry_apps r
    WHERE ($2 IS NULL OR cardinality($2) = 0 OR r.tags && $2)
      AND ($3 IS NULL OR $3 = '' OR r.license = $3)
      AND (
        $1 IS NULL OR $1 = '' OR
        coalesce(r.name, '') ILIKE ('%' || $1 || '%') OR
        coalesce(r.description, '') ILIKE ('%' || $1 || '%') OR
        coalesce(r.readme, '') ILIKE ('%' || $1 || '%')
      )
    ORDER BY score DESC, r.name ASC
    LIMIT $4
  $q$;

  RETURN QUERY EXECUTE sql_text USING q, tags_filter, license_filter, limit_val;
END;
$$;

GRANT EXECUTE ON FUNCTION public.registry_search(text, text[], text, integer, text) TO anon;
GRANT EXECUTE ON FUNCTION public.registry_search(text, text[], text, integer, text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.registry_search(text, text[], text, integer, text) TO service_role;
