// Edge Function: login do dashboard web da Casa Dekora.
// Valida e-mail/senha contra a tabela usuarios (hash bcrypt, a mesma do
// Streamlit) e emite um token assinado (HS256) valido por 7 dias.
// A chave de assinatura e derivada da service role key e nunca sai do servidor.
import postgres from "npm:postgres@3.4.5";
import bcrypt from "npm:bcryptjs@2.4.3";
import { SignJWT } from "npm:jose@5.9.6";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
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

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ erro: "Método não permitido." }, 405);

  let body: { email?: string; senha?: string };
  try {
    body = await req.json();
  } catch {
    return json({ erro: "Corpo inválido." }, 400);
  }
  const email = String(body.email ?? "").toLowerCase().trim();
  const senha = String(body.senha ?? "");
  if (!email || !senha) return json({ erro: "Informe e-mail e senha." }, 400);

  const sql = postgres(Deno.env.get("SUPABASE_DB_URL")!, { prepare: false });
  try {
    const rows =
      await sql`select email, senha_hash, nome from usuarios where email = ${email}`;
    if (!rows.length || !bcrypt.compareSync(senha, rows[0].senha_hash)) {
      return json({ erro: "E-mail ou senha incorretos." }, 401);
    }
    const token = await new SignJWT({ email: rows[0].email, nome: rows[0].nome })
      .setProtectedHeader({ alg: "HS256" })
      .setIssuedAt()
      .setExpirationTime("7d")
      .sign(await chaveAssinatura());
    return json({ token, nome: rows[0].nome, email: rows[0].email });
  } catch (e) {
    console.error("login: erro inesperado", e);
    return json({ erro: "Erro interno. Tente novamente." }, 500);
  } finally {
    await sql.end();
  }
});
