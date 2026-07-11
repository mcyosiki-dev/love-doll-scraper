import sqlite3
import shutil
from datetime import datetime

def normalize_materials():
    # バックアップを作成（念のため）
    backup_name = f"dolls_backup_before_material_normalize_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2('dolls.db', backup_name)
    print(f"✅ バックアップ作成: {backup_name}")

    # ★ マッピングを拡張（シリコン＋TPE と シリコン＆TPE を追加）
    mapping = {
        # シリコン系
        'シリコン': 'シリコン',
        'シリコーン': 'シリコン',
        'Silicon': 'シリコン',
        'silicon': 'シリコン',
        'Silicone': 'シリコン',
        'silicone': 'シリコン',
        'シリコン製': 'シリコン',
        # TPE系
        'TPE': 'TPE',
        'Tpe': 'TPE',
        'tpe': 'TPE',
        'TPE製': 'TPE',
        # ★ 混合材質（新規追加）
        'シリコン＋TPE': 'シリコン/TPE',
        'シリコン＆TPE': 'シリコン/TPE',
        'シリコン+TPE': 'シリコン/TPE',
        'シリコン&TPE': 'シリコン/TPE',
        # その他は必要に応じて追加
    }

    conn = sqlite3.connect('dolls.db')
    c = conn.cursor()

    # 現在の材質値の種類数を表示
    c.execute('SELECT DISTINCT spec_value FROM specs WHERE spec_key = "材質"')
    before = [row[0] for row in c.fetchall()]
    print(f"📊 更新前の材質値の種類: {len(before)} 件")

    # 更新を実行
    updated_count = 0
    for old_val, new_val in mapping.items():
        if old_val == new_val:
            continue
        c.execute('''
            UPDATE specs 
            SET spec_value = ? 
            WHERE spec_key = '材質' AND spec_value = ?
        ''', (new_val, old_val))
        updated_count += c.rowcount
        if c.rowcount > 0:
            print(f"  {old_val} → {new_val}: {c.rowcount} 件更新")

    conn.commit()
    conn.close()

    print(f"✅ 合計 {updated_count} 件の材質値を統一しました。")
    print("✅ データベースを更新しました。")

if __name__ == "__main__":
    normalize_materials()