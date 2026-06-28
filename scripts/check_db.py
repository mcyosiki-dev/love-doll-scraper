import sqlite3

conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()

# 商品テーブルの中身をすべて表示
cursor.execute('SELECT * FROM products')
rows = cursor.fetchall()

print("=== 商品一覧 ===")
for row in rows:
    print(f"ID: {row[0]}, 名前: {row[1]}, 価格: {row[2]}円, カテゴリ: {row[4]}")

# スペックテーブルの中身も表示（最初の5件だけ）
print("\n=== スペック例（最初の5件） ===")
cursor.execute('SELECT * FROM specs LIMIT 5')
specs = cursor.fetchall()
for spec in specs:
    print(f"商品ID: {spec[1]}, キー: {spec[2]}, 値: {spec[3]}")

conn.close()