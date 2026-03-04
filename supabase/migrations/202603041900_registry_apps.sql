-- Core table and indexes for self-hosted registry ingestion

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_trgm') THEN
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
    CREATE EXTENSION IF NOT EXISTS vector;
  END IF;
END
$$;

CREATE TABLE IF NOT EXISTS public.registry_apps (
  id text PRIMARY KEY,
  name text,
  description text,
  tags text[] DEFAULT '{}'::text[],
  license text,
  repo_url text,
  homepage_url text,
  readme text,
  raw jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    BEGIN
      ALTER TABLE public.registry_apps ADD COLUMN IF NOT EXISTS embedding vector(1536) NULL;
    EXCEPTION WHEN undefined_object THEN
      NULL;
    END;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS registry_apps_tags_gin_idx
  ON public.registry_apps USING gin (tags);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
    CREATE INDEX IF NOT EXISTS registry_apps_name_trgm_idx
      ON public.registry_apps USING gin (name gin_trgm_ops);

    CREATE INDEX IF NOT EXISTS registry_apps_description_trgm_idx
      ON public.registry_apps USING gin (description gin_trgm_ops);
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
     AND EXISTS (
       SELECT 1
       FROM information_schema.columns
       WHERE table_schema = 'public'
         AND table_name = 'registry_apps'
         AND column_name = 'embedding'
     ) THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS registry_apps_embedding_ivfflat_idx
             ON public.registry_apps
             USING ivfflat (embedding vector_cosine_ops)
             WITH (lists = 100)';
  END IF;
END
$$;
