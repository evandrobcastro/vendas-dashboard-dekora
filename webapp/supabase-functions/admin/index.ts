// Edge Function: acoes administrativas do dashboard web (token obrigatorio).
//   GET  -> status da fila de sincronizacao (em andamento? ultimo pedido)
//   POST {acao:"meta", tipo_kpi, vendedor, ano_mes, valor_meta} -> upsert de 1 meta
//   POST {acao:"metas_lote", linhas:[{...}]} -> upsert em lote (max 200)
//   POST {acao:"sync", dias} -> enfileira pedido de sincronizacao p/ o PC
import postgres from "npm:postgres@3.4.5";
import { jwtVerify } from "npm:jose@5.9.6";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

async function chaveAssinatura(): Promise<Uint8Array> {
  const material =
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")! + "|cd-dashboard-token-v1";
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(material),
  );
  return new Uint8Array(digest);
}

const VENDEDOR_GERAL = "GERAL";

async function upsertMeta(sql: any, linha: any): Promise<void> {
  const tipoKpi = String(linha.tipo_kpi ?? "").trim();
  const vendedor = String(linha.vendedor ?? "").trim() || VENDEDOR_GERAL;
  const anoMes = String(linha.ano_mes ?? "").trim();
  const valor = Number(linha.valor_meta);
  if (!tipoKpi) throw new Error("informe o KPI");
  if (!/^\d{4}-\d{2}$/.test(anoMes)) throw new Error("ano_mes deve ser AAAA-MM");
  if (!Number.isFinite(valor) || valor < 0) throw new Error("valor da meta inválido");
  await sql`
    insert into metas (tipo_kpi, vendedor, ano_mes, valor_meta, criado_em, atualizado_em)
    values (${tipoKpi}, ${vendedor}, ${anoMes}, ${valor}, current_timestamp, current_timestamp)
    on conflict (tipo_kpi, vendedor, ano_mes)
    do update set valor_meta = excluded.valor_meta, atualizado_em = current_timestamp`;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const auth = req.headers.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  let usuario: string;
  try {
    const { payload } = await jwtVerify(token, await chaveAssinatura());
    usuario = String(payload.email ?? "");
  } catch {
    return json({ erro: "Sessão inválida ou expirada. Entre novamente." }, 401);
  }

  const sql = postgres(Deno.env.get("SUPABASE_DB_URL")!, { prepare: false });
  try {
    if (req.method === "GET") {
      const andamento = await sql`
        select 1 from pedidos_sync where status in ('pendente','processando') limit 1`;
      const ultimo = await sql`
        select status, mensagem, atualizado_em, solicitado_por
        from pedidos_sync order by id desc limit 1`;
      return json({ em_andamento: andamento.length > 0, ultimo: ultimo[0] ?? null });
    }

    if (req.method !== "POST") return json({ erro: "Método não permitido." }, 405);
    let body: any;
    try {
      body = await req.json();
    } catch {
      return json({ erro: "Corpo inválido." }, 400);
    }

    if (body.acao === "meta") {
      try {
        await upsertMeta(sql, body);
        return json({ ok: true });
      } catch (e) {
        return json({ erro: (e as Error).message }, 400);
      }
    }

    if (body.acao === "metas_lote") {
      const linhas = Array.isArray(body.linhas) ? body.linhas.slice(0, 200) : [];
      let sucesso = 0;
      const erros: string[] = [];
      for (let i = 0; i < linhas.length; i++) {
        try {
          await upsertMeta(sql, linhas[i]);
          sucesso++;
        } catch (e) {
          erros.push(`Linha ${i + 1}: ${(e as Error).message}`);
        }
      }
      return json({ sucesso, erros });
    }

    if (body.acao === "sync") {
      const dias = Math.max(Math.trunc(Number(body.dias) || 0), 0);
      const andamento = await sql`
        select 1 from pedidos_sync where status in ('pendente','processando') limit 1`;
      if (andamento.length) return json({ em_andamento: true }, 409);
      await sql`
        insert into pedidos_sync (solicitado_por, dias, status)
        values (${usuario}, ${dias}, 'pendente')`;
      return json({ ok: true });
    }

    return json({ erro: "Ação desconhecida." }, 400);
  } catch (e) {
    console.error("admin: erro inesperado", e);
    return json({ erro: "Erro interno. Tente novamente." }, 500);
  } finally {
    await sql.end();
  }
});
