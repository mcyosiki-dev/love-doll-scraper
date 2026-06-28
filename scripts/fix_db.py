import sqlite3

conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()

# 削除対象のID（582 から 597 まで）
delete_ids = list(range(582, 598))

for pid in delete_ids:
    cursor.execute('DELETE FROM specs WHERE product_id = ?', (pid,))
    cursor.execute('DELETE FROM products WHERE id = ?', (pid,))
    print(f"✅ ID {pid} を削除しました。")

conn.commit()
conn.close()
print("✅ 不要データの削除が完了しました。")