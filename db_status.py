import sqlite3

conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()

# テーブル一覧を表示
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("=== DB内のテーブル一覧 ===")
if tables:
    for table in tables:
        print(f"  - {table[0]}")
else:
    print("  ⚠️ テーブルが一つもありません（データベースが空です）")

conn.close()

if not tables:
    print("\n👉 まだ json_to_db.py が実行されていない可能性が高いです。")
    print("👉 スクレイピング完了後に json_to_db.py を実行してください。")