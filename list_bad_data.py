import json

def is_bad(item):
    name = item.get('商品名', '')
    price = item.get('価格', '')
    url = item.get('商品URL', '')
    variants = item.get('スペックバリエーション', [])
    
    # 価格が異常
    if price in ['取得できず', '取得できず円', '0円', '10円', '']:
        return True
    
    # 商品名が不明または404
    if name in ['不明', '404 Page Not Found', 'Oops! That page can’t be found.']:
        return True
    
    # スペックが空またはすべての値が空
    if not variants:
        return True
    for variant in variants:
        # スペックのキーが大分類とサイト名だけしかない（実質空）
        keys = set(variant.keys())
        if keys <= {'大分類', 'サイト名'}:
            return True
        # すべてのスペック値が空または'-'の場合（リストは除外）
        all_empty = True
        for k, v in variant.items():
            if k in ['大分類', 'サイト名']:
                continue
            # 値がリストの場合はスキップ（ペニス情報など）
            if isinstance(v, list):
                continue
            if v and v != '-' and str(v).strip():
                all_empty = False
                break
        if all_empty:
            return True
    return False

with open('all_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

bad_items = []
for item in data:
    if is_bad(item):
        bad_items.append({
            '商品名': item.get('商品名'),
            '価格': item.get('価格'),
            '商品URL': item.get('商品URL')
        })

print(f"📊 全商品数: {len(data)}")
print(f"🗑️ 不良データ件数: {len(bad_items)}")
print("\n--- 不良データ一覧（先頭20件） ---")
for i, item in enumerate(bad_items[:20], 1):
    print(f"{i}. {item['商品名'][:50]} ... ({item['商品URL']})")

if len(bad_items) > 20:
    print(f"... 他 {len(bad_items) - 20} 件")

with open('bad_data_list.txt', 'w', encoding='utf-8') as f:
    for item in bad_items:
        f.write(f"{item['商品URL']}\t{item['商品名']}\t{item['価格']}\n")
print("\n✅ 不良データのURL一覧を bad_data_list.txt に出力しました。")