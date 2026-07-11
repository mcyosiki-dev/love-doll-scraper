import sqlite3
import string

conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()

print("=" * 70)
print("【1. すべての spec_key 一覧】")
print("=" * 70)
cursor.execute("SELECT DISTINCT spec_key FROM specs ORDER BY spec_key")
keys = cursor.fetchall()
for k in keys:
    print(f"  {k[0]}")

print("\n" + "=" * 70)
print("【2. カップ数に関連する spec_key の値一覧（全値）】")
print("=" * 70)
cup_keys = ['カップ数', 'カップ', 'cup', 'CUP', 'バスト', 'トップバスト', 'サイズ', 'size']
for key in cup_keys:
    cursor.execute("SELECT DISTINCT spec_value FROM specs WHERE spec_key = ? ORDER BY spec_value", (key,))
    values = cursor.fetchall()
    if values:
        print(f"\n--- {key} ---")
        for v in values:
            print(f"    {v[0]}")

print("\n" + "=" * 70)
print("【3. spec_value に '以上' を含むレコード（全 spec_key）】")
print("=" * 70)
cursor.execute("""
    SELECT spec_key, spec_value, COUNT(*) 
    FROM specs 
    WHERE spec_value LIKE '%以上%' 
    GROUP BY spec_key, spec_value 
    ORDER BY spec_key, spec_value
""")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"  {row[0]}: {row[1]} ({row[2]}件)")
else:
    print("  （なし）")

print("\n" + "=" * 70)
print("【4. アルファベット（A〜Z）を含む spec_value のレコード（全 spec_key）】")
print("=" * 70)
for letter in string.ascii_uppercase:
    print(f"\n--- '{letter}' を含む値 ---")
    cursor.execute("""
        SELECT spec_key, spec_value, COUNT(*) 
        FROM specs 
        WHERE spec_value LIKE ? 
        GROUP BY spec_key, spec_value 
        ORDER BY spec_key, spec_value
    """, (f'%{letter}%',))
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"    {row[0]}: {row[1]} ({row[2]}件)")
    else:
        print(f"    （なし）")

print("\n" + "=" * 70)
print("【5. カップ数関連キーに存在する値の全リスト（重複除去）】")
print("=" * 70)
cup_keys_detected = ['カップ数', 'カップ', 'cup', 'CUP']
all_cup_values = set()
for key in cup_keys_detected:
    cursor.execute("SELECT DISTINCT spec_value FROM specs WHERE spec_key = ?", (key,))
    for row in cursor.fetchall():
        all_cup_values.add(row[0])
for val in sorted(all_cup_values):
    print(f"  {val}")

conn.close()