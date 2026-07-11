# -*- coding: utf-8 -*-
import json

with open('all_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

missing = []
for item in data:
    if not item.get('manufacturer'):
        missing.append({
            '商品名': item.get('商品名', '不明')[:60],
            '商品URL': item.get('商品URL', '不明')
        })

print(f"🔍 メーカー不明の商品: {len(missing)} 件")
for idx, item in enumerate(missing, 1):
    print(f"{idx}. {item['商品名']}")
    print(f"   URL: {item['商品URL']}")
    print()