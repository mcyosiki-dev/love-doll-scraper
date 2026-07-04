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

with open('all_data.json', 'r', encoding='utf-8') as f:
    products = json.load(f)

conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()

cursor.execute('DROP TABLE IF EXISTS specs')
cursor.execute('DROP TABLE IF EXISTS products')

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
        price_int INTEGER
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
    if not variants:
        continue

    for variant in variants:
        category = variant.get('大分類', '不明')
        height_cm = extract_num(variant.get('身長', ''))
        weight_kg = extract_num(variant.get('体重', ''))
        foot_cm = extract_num(variant.get('足のサイズ', ''))
        price_int = extract_num(price)

        try:
            cursor.execute('''
                INSERT INTO products (name, price, url, category, height_cm, weight_kg, foot_cm, price_int)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, price, url, category, height_cm, weight_kg, foot_cm, price_int))
            product_id = cursor.lastrowid
        except Exception as e:
            print(f"⚠️ 商品挿入エラー: {e} (URL: {url})")
            continue

        for key, value in variant.items():
            if key == '大分類':
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
                print(f"⚠️ スペック挿入エラー: {e} (キー: {key})")
        total_variants += 1

conn.commit()
conn.close()

print(f"✅ {len(products)} 件の商品から {total_variants} 件のバリエーションをデータベース（dolls.db）に保存しました。")