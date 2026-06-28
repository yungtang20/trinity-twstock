import requests
import json

r1 = requests.get('https://www.twse.com.tw/rwd/zh/fund/T86', params={'response':'json','date':'20240625','selectType':'ALLBUT0999'})
r2 = requests.get('https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX', params={'response':'json','date':'20240625','type':'ALL'})
t_all = r2.json().get('tables', [])
mi_fields = next((t['fields'] for t in t_all if '每日收盤行情' in t.get('title', '')), [])
r3 = requests.get('https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php', params={'l': 'zh-tw', 'd': '113/06/25', 'se': 'AL', 's': '0,asc,0'})

data = {
    'T86': r1.json().get('fields'),
    'MI_INDEX': mi_fields,
    'Quotes': r3.json().get('tables', [{}])[0].get('fields')
}

with open('fields.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
