import { Client } from "pg";
async function test() {
  const connectionString = "postgres://postgres.fpodvtaiugvgyfundequ:sk_54797faf7a65eee079b243b424e39f5e0347de0307b4a4735a970265d1a76f82@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres";
  const client = new Client({ connectionString });
  try {
    await client.connect();
    const res = await client.query('SELECT NOW()');
    console.log("Connected to postgres! Time:", res.rows[0]);
    await client.end();
  } catch (e) {
    console.error("Failed to connect:", e);
  }
}
test();
