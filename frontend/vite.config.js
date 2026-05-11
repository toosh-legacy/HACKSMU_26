import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';
import { createReadStream, existsSync, statSync } from 'fs';
import { execFile } from 'child_process';

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        login: path.resolve(__dirname, 'login.html'),
        signup: path.resolve(__dirname, 'signup.html'),
      },
    },
  },
  server: {
    port: 5173,
    open: true,
    proxy: {
      // Forward all /api/* requests to the Python upload server
      '/api': {
        target: 'http://localhost:5050',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
  publicDir: 'public',
  resolve: {
    alias: {
      '@results': path.resolve(__dirname, '../rumbleos/results'),
    },
  },
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'generate-hypotheses',
      configureServer(server) {
        const rumbleosDir = path.resolve(__dirname, '../rumbleos');
        server.middlewares.use('/api/generate-hypotheses', (req, res, next) => {
          if (req.method !== 'POST') { next(); return; }
          res.setHeader('Content-Type', 'application/json');
          execFile('python', ['gen_hypotheses.py'], { cwd: rumbleosDir }, (err, stdout, stderr) => {
            if (err) {
              res.statusCode = 500;
              res.end(JSON.stringify({ error: stderr || err.message }));
            } else {
              res.end(JSON.stringify({ ok: true }));
            }
          });
        });
      },
    },
    {
      name: 'serve-results',
      configureServer(server) {
        // ── /results static files ─────────────────────────────────
        const resultsDir = path.resolve(__dirname, '../rumbleos/results');
        server.middlewares.use('/results', (req, res, next) => {
          const filePath = path.join(resultsDir, decodeURIComponent(req.url));
          if (existsSync(filePath) && statSync(filePath).isFile()) {
            const mimeTypes = {
              '.png': 'image/png', '.jpg': 'image/jpeg',
              '.wav': 'audio/wav', '.csv': 'text/csv',
              '.json': 'application/json', '.txt': 'text/plain',
            };
            res.setHeader(
              'Content-Type',
              mimeTypes[path.extname(filePath).toLowerCase()] || 'application/octet-stream'
            );
            createReadStream(filePath).pipe(res);
          } else {
            next();
          }
        });
      },
    },
  ],
});
