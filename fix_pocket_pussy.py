import sqlite3
conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()
cursor.execute("UPDATE products SET category = 'オナホール' WHERE name LIKE '%Pocket Pussy%'")
conn.commit()
print(f"✅ {cursor.rowcount}件のPocket Pussyを「オナホール」に修正しました。")
conn.close()