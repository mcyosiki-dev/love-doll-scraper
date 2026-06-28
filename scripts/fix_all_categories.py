import sqlite3

conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()

# 全商品のIDと商品名を取得
cursor.execute('SELECT id, name FROM products')
products = cursor.fetchall()

updated_count = 0

for pid, name in products:
    # 商品名に基づいてカテゴリを判定
    if 'オナホール' in name:
        new_category = 'オナホール'
    elif 'トルソー' in name:
        new_category = 'トルソー'
    else:
        new_category = '女性型'  # デフォルト
    
    # 更新を実行
    cursor.execute('UPDATE products SET category = ? WHERE id = ?', (new_category, pid))
    updated_count += 1

conn.commit()
conn.close()

print(f"✅ {updated_count}件のカテゴリを再判定・更新しました。")