import express from 'express';
import path from 'path';
import { initializeDatabase } from './db';
import { stockRouter, marketRouter, dashboardRouter, strategyRouter, syncRouter, settingsRouter, aiRouter } from './routes';

export async function createApp() {
  const app = express();

  // Initialize database
  await initializeDatabase();

  // CORS middleware
  app.use((req, res, next) => {
    const origin = req.headers.origin;
    if (origin) {
      res.setHeader('Access-Control-Allow-Origin', origin);
    } else {
      res.setHeader('Access-Control-Allow-Origin', '*');
    }
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, PATCH, DELETE');
    res.setHeader('Access-Control-Allow-Headers', 'X-Requested-With,Content-Type,Authorization,Accept,Origin');
    res.setHeader('Access-Control-Allow-Credentials', 'true');
    if (req.method === 'OPTIONS') {
      return res.sendStatus(200);
    }
    next();
  });

  app.use(express.json({ limit: '50mb' }));

  // Register routes
  app.use('/api/stock', stockRouter);
  app.use('/api', marketRouter);
  app.use('/api/dashboard', dashboardRouter);
  app.use('/api/strategy', strategyRouter);
  app.use('/api', syncRouter);
  app.use('/api', settingsRouter);
  app.use('/api', aiRouter);

  // Vite / Static files
  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  return app;
}
