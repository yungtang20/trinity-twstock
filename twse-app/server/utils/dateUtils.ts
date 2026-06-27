export const formatDateStr = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}${m}${d}`;
};

export const formatTpexDateStr = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}/${m}/${d}`;
};

export const getTradingDays = (n: number): string[] => {
  const dates: string[] = [];
  const curr = new Date();
  curr.setHours(12, 0, 0, 0);
  while (dates.length < n) {
    const day = curr.getDay();
    if (day !== 0 && day !== 6) {
      dates.push(curr.toISOString().split('T')[0]);
    }
    curr.setDate(curr.getDate() - 1);
  }
  return dates.reverse();
};

export function makeSeedRandom(seedStr: string) {
  let h = 0;
  for (let i = 0; i < seedStr.length; i++) {
    h = (h * 31 + seedStr.charCodeAt(i)) | 0;
  }
  return function () {
    h = Math.sin(h) * 10000;
    return h - Math.floor(h);
  };
}
