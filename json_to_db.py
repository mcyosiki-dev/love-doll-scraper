import json
import sqlite3
import re

def extract_num(val):
    if not val:
        return None
    match = re.search(r'([\d.]+)', str(val))
    if match:
        return float(match.group(1))
    return None

# カップ数正規化マッピング
CUP_NORMALIZE = {
    'AA': 'AA', 'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E', 'F': 'F',
    'G': 'G', 'G以上': 'G', 'Gカップ': 'G',
    'H': 'H', 'I': 'I', 'J': 'J', 'K': 'K', 'L': 'L',
    'M以上': 'M以上', 'M': 'M以上',
}

# 材質マッピング（既存）
MATERIAL_MAPPING = {
    'シリコン': 'シリコン',
    'シリコン+TPE': 'シリコン+TPE',
    # 必要に応じて追加
}

EXCLUDED_MATERIALS = ['身長']

with open('all_data.json', 'r', encoding='utf-8') as f:
    products = json.load(f)

conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()

cursor.execute('DROP TABLE IF EXISTS specs')
cursor.execute('DROP TABLE IF EXISTS products')

# ★ 2026-07-09 カラム追加：manufacturer, site_product_id（image_urlは非収集）
cursor.execute('''
    CREATE TABLE products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price TEXT,
        url TEXT,
        category TEXT,
        height_cm REAL,
        weight_kg REAL,
        foot_cm REAL,
        price_int INTEGER,
        manufacturer TEXT,
        site_product_id TEXT
    )
''')

cursor.execute('''
    CREATE TABLE specs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        spec_key TEXT,
        spec_value TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    )
''')

total_variants = 0

for product in products:
    name = product.get('商品名', '')
    price = product.get('価格', '')
    url = product.get('商品URL', '')
    variants = product.get('スペックバリエーション', [])
    manufacturer = product.get('manufacturer', None)
    site_product_id = product.get('site_product_id', None)
    
    if not variants:
        continue

    for variant in variants:
        category = variant.get('大分類', '不明')

        # 材質正規化
        if '材質' in variant:
            raw_material = variant['材質']
            if raw_material in MATERIAL_MAPPING:
                variant['材質'] = MATERIAL_MAPPING[raw_material]
            if variant['材質'] in EXCLUDED_MATERIALS:
                del variant['材質']

        # カップ数正規化
        if 'カップ数' in variant:
            raw_cup = variant['カップ数']
            if raw_cup in CUP_NORMALIZE:
                variant['カップ数'] = CUP_NORMALIZE[raw_cup]

        height_raw = variant.get('身長') or variant.get('高さ')
        weight_raw = variant.get('体重') or variant.get('重さ')
        foot_raw = variant.get('足のサイズ') or variant.get('足サイズ')

        height_cm = extract_num(height_raw)
        weight_kg = extract_num(weight_raw)
        foot_cm = extract_num(foot_raw)
        price_int = extract_num(price)

        try:
            cursor.execute('''
                INSERT INTO products (
                    name, price, url, category,
                    height_cm, weight_kg, foot_cm, price_int,
                    manufacturer, site_product_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, price, url, category,
                  height_cm, weight_kg, foot_cm, price_int,
                  manufacturer, site_product_id))
            product_id = cursor.lastrowid
        except Exception as e:
            print(f"商品挿入エラー: {e} (URL: {url})")
            continue

        for key, value in variant.items():
            if key == '大分類':
                continue
            if key == '材質' and value in EXCLUDED_MATERIALS:
                continue
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False)
            else:
                value = str(value)
            try:
                cursor.execute('''
                    INSERT INTO specs (product_id, spec_key, spec_value)
                    VALUES (?, ?, ?)
                ''', (product_id, key, value))
            except Exception as e:
                print(f"スペック挿入エラー: {e} (キー: {key})")
        total_variants += 1

conn.commit()
conn.close()

print(f"✅ {len(products)} 件の商品から {total_variants} 件のバリエーションをデータベース（dolls.db）に保存しました。")