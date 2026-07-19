import sqlite3
import re

conn = sqlite3.connect('dolls.db')
cursor = conn.cursor()

# バックアップを取る
conn.execute("BEGIN IMMEDIATE")
cursor.execute("SELECT COUNT(*) FROM specs WHERE spec_key='材質'")
total = cursor.fetchone()[0]
print(f"📊 材質データ総数: {total} 件")

def normalize_material(value):
    if not value:
        return None
    # 30文字以内の場合、既存のマッピングに従う
    if len(value) <= 30:
        # エラストマー → TPE
        if 'エラストマー' in value:
            return 'TPE'
        # シリコン系
        if 'シリコン' in value or 'Silicon' in value or 'Silicone' in value:
            if 'TPE' in value:
                return 'シリコン+TPE'
            return 'シリコン'
        if 'TPE' in value:
            return 'TPE'
        if 'PVC' in value:
            return 'PVC'
        if 'STPE' in value:
            return 'STPE'
        if 'ビニール' in value or 'ソフビ' in value:
            return 'ビニール'
        return value
    # 30文字超の長文はキーワード抽出
    if 'シリコン' in value or 'Silicon' in value:
        if 'TPE' in value:
            return 'シリコン+TPE'
        return 'シリコン'
    if 'TPE' in value:
        return 'TPE'
    if 'PVC' in value:
        return 'PVC'
    if 'STPE' in value:
        return 'STPE'
    if 'ビニール' in value or 'ソフビ' in value:
        return 'ビニール'
    # 該当しない長文は削除
    return None

updated = 0
deleted = 0
cursor.execute("SELECT id, spec_value FROM specs WHERE spec_key='材質'")
rows = cursor.fetchall()

for row in rows:
    sid = row[0]
    original = row[1]
    normalized = normalize_material(original)
    if normalized is None:
        cursor.execute("DELETE FROM specs WHERE id = ?", (sid,))
        deleted += 1
    elif normalized != original:
        cursor.execute("UPDATE specs SET spec_value = ? WHERE id = ?", (normalized, sid))
        updated += 1

conn.commit()
conn.close()

print(f"✅ 材質クレンジング完了")
print(f"   更新: {updated} 件")
print(f"   削除: {deleted} 件")
print(f"   残存: {total - deleted} 件（更新後）")