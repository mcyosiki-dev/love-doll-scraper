import sqlite3
conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()

# シリコン系を統一
cursor.execute("UPDATE specs SET spec_value = 'シリコン' WHERE spec_key = '材質' AND (spec_value LIKE '%Silicon%' OR spec_value LIKE '%silicon%' OR spec_value = 'シリコン' OR spec_value = 'シリコーン')")

# シリコン＋TPE と シリコン＆TPE を「シリコン/TPE」に統一
cursor.execute("UPDATE specs SET spec_value = 'シリコン/TPE' WHERE spec_key = '材質' AND (spec_value LIKE '%シリコン＋TPE%' OR spec_value LIKE '%シリコン＆TPE%' OR spec_value LIKE '%シリコン+TPE%' OR spec_value LIKE '%シリコン&TPE%')")

conn.commit()
conn.close()
print("✅ 材質表記を統一しました（シリコン / シリコン/TPE）")