// Edge Function: entrega os dados do dashboard (registros + metas) em JSON
// compacto, somente para requisicoes com token valido emitido pelo /login.
// Nomes (vendedor/cidade/cliente) saem ja normalizados (trim), como no app.py.
import postgres from "npm:postgres@3.4.5";
import { jwtVerify } from "npm:jose@5.9.6";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
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

const COLS_REGISTROS = [
  "codigo", "tipo", "cliente", "identificacao", "situacao", "valor",
  "vendedor", "desconto", "data_cadastro", "data_aprovacao", "dias_aprovacao",
  "metragem", "cidade", "valor_sem_desc", "segmento", "comissionado",
  "forma_divulgacao",
];
const COLS_METAS = ["tipo_kpi", "vendedor", "ano_mes", "valor_meta", "atualizado_em"];
const COLS_LOG = ["executado_em", "linhas_novas", "linhas_atualizadas",
                  "linhas_removidas", "status", "mensagem"];
const COLS_PRODUTOS = ["ano_mes", "classe", "subclasse", "quantidade",
                       "m2_vidro", "m2_inst", "peso_perfil", "valor_venda",
                       "valor_custo", "lucro"];

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "GET") return json({ erro: "Método não permitido." }, 405);

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
    const registros = await sql`
      select codigo, tipo, trim(cliente) as cliente, identificacao, situacao,
             valor, trim(vendedor) as vendedor, desconto, data_cadastro,
             data_aprovacao, dias_aprovacao, metragem, trim(cidade) as cidade,
             valor_sem_desc, segmento, comissionado, forma_divulgacao
      from registros`;
    const metas = await sql`
      select tipo_kpi, vendedor, ano_mes, valor_meta, atualizado_em from metas`;
    const sync = await sql`
      select max(executado_em) as ultima from sync_log where status = 'sucesso'`;
    const syncLog = await sql`
      select executado_em, linhas_novas, linhas_atualizadas, linhas_removidas,
             status, mensagem
      from sync_log order by executado_em desc limit 20`;
    let produtos: any[] = [];
    try {
      produtos = await sql`
        select ano_mes, classe, subclasse, quantidade, m2_vidro, m2_inst,
               peso_perfil, valor_venda, valor_custo, lucro
        from produtos`;
    } catch (_e) {
      // tabela produtos ainda nao existe: segue sem ela
    }

    return json({
      usuario,
      gerado_em: new Date().toISOString(),
      ultima_sincronizacao: sync[0]?.ultima ?? null,
      registros: {
        columns: COLS_REGISTROS,
        rows: registros.map((r) => COLS_REGISTROS.map((c) => r[c] ?? null)),
      },
      metas: {
        columns: COLS_METAS,
        rows: metas.map((r) => COLS_METAS.map((c) => r[c] ?? null)),
      },
      sync_log: {
        columns: COLS_LOG,
        rows: syncLog.map((r) => COLS_LOG.map((c) => r[c] ?? null)),
      },
      produtos: {
        columns: COLS_PRODUTOS,
        rows: produtos.map((r) => COLS_PRODUTOS.map((c) => r[c] ?? null)),
      },
    });
  } catch (e) {
    console.error("dados: erro inesperado", e);
    return json({ erro: "Erro interno. Tente novamente." }, 500);
  } finally {
    await sql.end();
  }
});
