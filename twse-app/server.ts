import dotenv from "dotenv";
dotenv.config();

import { createApp } from "./src/server/app";
import { attachVite } from "./src/server/vite-dev";
import { getDb } from "./src/server/lib/db";

async function startServer() {
  const PORT = 3000;

  // Initialize database (eager connect on startup)
  getDb();

  const app = createApp();
  await attachVite(app);

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`[FULL-STACK] Express server running on http://localhost:${PORT}`);
  });
}

startServer().catch((err) => {
  console.error("Failed to start server:", err);
  process.exit(1);
});
