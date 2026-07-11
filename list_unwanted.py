import json
import re

def is_unwanted(product_name, html_text=""):
    text = product_name + " " + html_text
    # オナホールとトルソーは絶対に削除しない（優先）
    if "オナホール" in text or "トルソー" in text:
        return False
    # 削除対象
    if "里帰り" in product_name or "受付" in product_name:
        return True
    if "404" in product_name or "Page Not Found" in product_name:
        return True
    for kw in ["福袋", "ランダムセット", "ヘッド単体", "ヘッド単品", "ボディ単体"]:
        if kw in text:
            return True
    return False

# all_data.json を読み込む
with open('all_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

unwanted = []
for item in data:
    name = item.get('商品名', '')
    url = item.get('商品URL', '')
    if is_unwanted(name):
        unwanted.append({
            '商品名': name,
            '商品URL': url
        })

print(f"📊 全商品数: {len(data)} 件")
print(f"🗑️ 不要と判定された商品数: {len(unwanted)} 件")
print("\n--- 不要データ一覧（先頭20件） ---")
for i, item in enumerate(unwanted[:20], 1):
    print(f"{i}. {item['商品名'][:50]}... ({item['商品URL']})")

if len(unwanted) > 20:
    print(f"... 他 {len(unwanted) - 20} 件")

# 確認用にファイル出力も行う
with open('unwanted_list.txt', 'w', encoding='utf-8') as f:
    for item in unwanted:
        f.write(f"{item['商品URL']}\t{item['商品名']}\n")
print("\n✅ 不要データのURL一覧を unwanted_list.txt に出力しました。")