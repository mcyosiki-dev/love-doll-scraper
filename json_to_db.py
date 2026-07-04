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

# ★【2026-07-04 修正】材質正規化マッピング（WebAI様からの確定版・再修正）
MATERIAL_MAPPING = {
    # 基本素材（単独）
    'シリコン': 'シリコン',
    'フルシリコン': 'シリコン',
    'シリコン製': 'シリコン',
    'シリコンボディ': 'シリコン',
    'TPE': 'TPE',
    'TPE製': 'TPE',
    'STPE': 'S-TPE',
    'S-TPE': 'S-TPE',
    'PVC': 'PVC',
    'レジン': 'レジン',
    # 組み合わせ（+表記） → すべて「シリコン+TPE」に統一
    'シリコン+TPE': 'シリコン+TPE',
    'シリコン＋TPE': 'シリコン+TPE',
    'シリコン＆TPE': 'シリコン+TPE',
    'シリコン&TPE': 'シリコン+TPE',
    'Silicon+TPE': 'シリコン+TPE',
    'TPE+シリコン': 'シリコン+TPE',
    'TPE製＋シリコン製': 'シリコン+TPE',
    'silicon head+TPE body': 'シリコン+TPE',
    'シリコンヘッド+TPEボディ': 'シリコン+TPE',
    'シリコンヘッド＋TPEボディ': 'シリコン+TPE',
    'シリコンヘッド + TPEボディ': 'シリコン+TPE',
    # シリコン + S-TPE
    'シリコン+S-TPE': 'シリコン+S-TPE',
    'Silicon/Silicon+TPE': 'シリコン+S-TPE',
    # PVC + シリコン
    'PVC+シリコン': 'PVC+シリコン',
    'シリコンボディ＋PVC頭部': 'PVC+シリコン',
    # PVC + TPE
    'PVC+TPE': 'PVC+TPE',
    # レジン + シリコン
    'レジン＋silicon': 'レジン+シリコン',
}

# ★ 材質フィルタから除外する値（ノイズ）
EXCLUDED_MATERIALS = ['身長']

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

        # ★ 材質を正規化
        if '材質' in variant:
            raw_material = variant['材質']
            if raw_material in MATERIAL_MAPPING:
                variant['材質'] = MATERIAL_MAPPING[raw_material]
            # ★ 除外対象の材質は削除（specsに保存しない）
            if variant['材質'] in EXCLUDED_MATERIALS:
                del variant['材質']

        # ★ フォールバックマッピング：高さ→身長、重さ→体重
        height_raw = variant.get('身長') or variant.get('高さ')
        weight_raw = variant.get('体重') or variant.get('重さ')
        foot_raw = variant.get('足のサイズ') or variant.get('足サイズ')

        height_cm = extract_num(height_raw)
        weight_kg = extract_num(weight_raw)
        foot_cm = extract_num(foot_raw)
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
            # ★ 除外対象の材質はスキップ（安全のため二重チェック）
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
                print(f"⚠️ スペック挿入エラー: {e} (キー: {key})")
        total_variants += 1

conn.commit()
conn.close()

print(f"✅ {len(products)} 件の商品から {total_variants} 件のバリエーションをデータベース（dolls.db）に保存しました。")