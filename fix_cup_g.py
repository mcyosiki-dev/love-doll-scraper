# fix_cup_g.py
import sqlite3

def fix_cup_g():
    conn = sqlite3.connect('dolls.db')
    c = conn.cursor()
    c.execute("UPDATE specs SET spec_value = 'G' WHERE spec_key = 'カップ数' AND spec_value = 'G以上'")
    conn.commit()
    rows = c.rowcount
    conn.close()
    print(f"✅ {rows} 件のレコードを「G」に更新しました。")

if __name__ == "__main__":
    fix_cup_g()