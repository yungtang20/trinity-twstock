import { createApp } from './app';

const PORT = parseInt(process.env.PORT || '3000', 10);

createApp().then((app) => {
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[FULL-STACK] Express server running on http://localhost:${PORT}`);
  });
});
