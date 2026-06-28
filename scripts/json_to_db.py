import json
import sqlite3

# --- JSONを読み込む ---
with open('all_data.json', 'r', encoding='utf-8') as f:
    products = json.load(f)

# --- データベースに接続 ---
conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()

# --- テーブル作成 ---
cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price TEXT,
        url TEXT UNIQUE,
        category TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS specs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        spec_key TEXT,
        spec_value TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    )
''')

# --- データ挿入 ---
for product in products:
    # 商品情報を取得
    name = product.get('商品名', '')
    price = product.get('価格', '')
    url = product.get('商品URL', '')
    
    # スペック情報を取得（大分類は別途取り出す）
    spec_list = product.get('スペックバリエーション', [])
    if not spec_list:
        continue
    
    spec = spec_list[0]
    category = spec.get('大分類', '不明')
    
    # 商品テーブルに挿入
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO products (name, price, url, category)
            VALUES (?, ?, ?, ?)
        ''', (name, price, url, category))
        product_id = cursor.lastrowid
    except Exception as e:
        print(f"⚠️ 商品挿入エラー: {e} (URL: {url})")
        continue
    
    # スペックを挿入（大分類はスキップ）
    for key, value in spec.items():
        if key == '大分類':
            continue
        
        # ★ 値がリストや辞書の場合はJSON文字列に変換 ★
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        else:
            value = str(value)  # 念のため文字列化
        
        try:
            cursor.execute('''
                INSERT INTO specs (product_id, spec_key, spec_value)
                VALUES (?, ?, ?)
            ''', (product_id, key, value))
        except Exception as e:
            print(f"⚠️ スペック挿入エラー: {e} (キー: {key})")

# --- 保存して閉じる ---
conn.commit()
conn.close()

print(f"✅ {len(products)}件のデータをデータベース（dolls.db）に保存しました。")