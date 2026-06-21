import { API_CONFIG } from '../config/apis';

export async function fetchFinmindData(dataset: string, dataId: string, startDate: string, endDate?: string) {
  const token = typeof process !== 'undefined' ? process.env.VITE_FINMIND_API_KEY : (import.meta as any).env?.VITE_FINMIND_API_KEY;
  const finmindUrl = `${API_CONFIG.FINMIND_BASE_URL}?dataset=${dataset}&data_id=${dataId}&start_date=${startDate}${endDate ? `&end_date=${endDate}` : ''}&token=${token || ''}`;
  
  const res = await fetch(finmindUrl);
  if (!res.ok) throw new Error(`FinMind API error: ${res.statusText}`);
  return await res.json();
}
