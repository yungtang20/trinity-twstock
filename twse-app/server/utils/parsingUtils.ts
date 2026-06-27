export const stripHtml = (s: string) => String(s || '').replace(/<[^>]*>/g, '').trim();

export const parseNum = (s: any) => parseFloat(String(s || '').replace(/,/g, '')) || 0;

export const getNormalizedProp = (obj: any, candidates: string[]) => {
  if (!obj) return undefined;
  for (const c of candidates) {
    if (obj[c] !== undefined && obj[c] !== null) return obj[c];

    const cClean = c.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();
    for (const key of Object.keys(obj)) {
      const kClean = key.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();
      if (kClean === cClean && obj[key] !== undefined && obj[key] !== null) {
        return obj[key];
      }
    }
  }
  return undefined;
};

export const parseTwseIndex = (json: any) => {
  try {
    const table = json?.tables?.[0];
    if (!table?.data) return null;
    let row = table.data.find((r: any) => String(r[0]).includes('發行量加權股價指數'));
    if (!row) row = table.data[1];
    const index = parseNum(row[1]);
    const change = parseNum(row[3]);
    const changePercent = parseNum(row[4]);
    if (index <= 0) return null;
    return { index, change, changePercent };
  } catch {
    return null;
  }
};

export const parseTwseUpDown = (json: any) => {
  try {
    const table = json?.tables?.[7];
    if (!table?.data) return null;
    let limitUp = 0,
      up = 0,
      flat = 0,
      down = 0,
      limitDown = 0;
    for (const row of table.data) {
      const type = String(row[0]);
      // row[1] = 整體市場, row[2] = 股票
      const marketCount = String(row[1] || '');
      const match = marketCount.match(/\((\d+)\)/);
      const count = parseNum(marketCount);
      const limit = match ? parseInt(match[1]) || 0 : 0;

      if (type.includes('上漲')) {
        up = count;
        limitUp = limit;
      } else if (type.includes('下跌')) {
        down = count;
        limitDown = limit;
      } else if (type.includes('持平')) {
        flat = count;
      }
    }
    return { limitUp, up, flat, down, limitDown };
  } catch {
    return null;
  }
};

export const parseTpexIndex = (json: any) => {
  try {
    const table = json?.tables?.[0];
    if (!table?.data?.[0]) return null;
    const row = table.data[table.data.length - 1];
    const index = parseNum(row[4]);
    const change = parseNum(row[5]);
    const changePercent = index !== 0 ? parseFloat(((change / (index - change)) * 100).toFixed(2)) : 0;
    if (index <= 0) return null;
    return { index, change, changePercent };
  } catch {
    return null;
  }
};
