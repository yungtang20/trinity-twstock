import https from 'https';
import http from 'http';

export function fetchFollowRedirects(
  url: string,
  maxRedirects = 5
): Promise<{ ok: boolean; status: number; json: () => Promise<any> }> {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.get(
      url,
      { headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json, text/javascript' } },
      (res) => {
        if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location && maxRedirects > 0) {
          let loc = res.headers.location;
          if (loc.startsWith('/')) {
            const p = new URL(url);
            loc = p.protocol + '//' + p.host + loc;
          }
          res.resume();
          return fetchFollowRedirects(loc, maxRedirects - 1).then(resolve).catch(reject);
        }
        resolve({
          ok: (res.statusCode || 0) >= 200 && (res.statusCode || 0) < 300,
          status: res.statusCode || 0,
          json: () =>
            new Promise((res2, rej) => {
              let d = '';
              res.on('data', (c) => (d += c));
              res.on('end', () => {
                try {
                  res2(JSON.parse(d));
                } catch (e) {
                  rej(e);
                }
              });
            }),
        });
      }
    );
    req.on('error', reject);
  });
}
