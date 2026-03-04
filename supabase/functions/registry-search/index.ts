import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

type SearchBody = {
  q?: string;
  tags?: string[];
  license?: string;
  limit?: number;
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
  const SUPABASE_SECRET_KEY = Deno.env.get("SUPABASE_SECRET_KEY") || "";
  const EMBEDDING_API_KEY = Deno.env.get("EMBEDDING_API_KEY") || "";
  const EMBEDDING_API_URL = Deno.env.get("EMBEDDING_API_URL") || "https://api.openai.com/v1/embeddings";
  const EMBEDDING_MODEL = Deno.env.get("EMBEDDING_MODEL") || "text-embedding-3-small";

  if (!SUPABASE_URL || !SUPABASE_SECRET_KEY) {
    return json({ error: "Supabase env not configured" }, 500);
  }

  const body = (await req.json().catch(() => ({}))) as SearchBody;
  const q = (body.q || "").trim();
  const tags = Array.isArray(body.tags) ? body.tags : null;
  const license = body.license || null;
  const limit = Number.isFinite(body.limit) ? Math.max(1, Math.min(100, Number(body.limit))) : 20;

  let queryEmbedding: string | null = null;
  if (q && EMBEDDING_API_KEY) {
    try {
      const r = await fetch(EMBEDDING_API_URL, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${EMBEDDING_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ model: EMBEDDING_MODEL, input: q }),
      });
      if (r.ok) {
        const payload = await r.json();
        const emb = payload?.data?.[0]?.embedding;
        if (Array.isArray(emb)) {
          queryEmbedding = `[${emb.map((x: number) => Number(x).toFixed(8)).join(",")}]`;
        }
      }
    } catch (_e) {
      // Non-fatal; fallback to trigram / text search
    }
  }

  const supabase = createClient(SUPABASE_URL, SUPABASE_SECRET_KEY, {
    auth: { persistSession: false },
  });

  const { data, error } = await supabase.rpc("registry_search", {
    q,
    tags_filter: tags,
    license_filter: license,
    match_limit: limit,
    query_embedding: queryEmbedding,
  });

  if (error) {
    return json({ error: error.message }, 500);
  }

  return json({
    query: { q, tags, license, limit, used_embedding: !!queryEmbedding },
    results: data || [],
  });
});

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      ...corsHeaders,
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}
