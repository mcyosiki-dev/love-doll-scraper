import sqlite3

conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()

# 男性型に更新（「男性」「メンズ」「Male」「男」を含み、「オナホール」を含まない）
cursor.execute('''
    UPDATE products
    SET category = '男性型'
    WHERE (name LIKE '%男性%'
           OR name LIKE '%メンズ%'
           OR name LIKE '%Male%'
           OR name LIKE '%男%')
      AND name NOT LIKE '%オナホール%'
''')
print(f"✅ {cursor.rowcount}件のカテゴリを「男性型」に更新しました。")

# 念のため、「男性型」に更新されたことを確認
cursor.execute('SELECT id, name, category FROM products WHERE category = "男性型" LIMIT 5')
rows = cursor.fetchall()
print("\n--- 更新後の確認（男性型の最初の5件） ---")
for row in rows:
    print(f"ID: {row[0]}, 名前: {row[1][:30]}..., カテゴリ: {row[2]}")

conn.commit()
conn.close()