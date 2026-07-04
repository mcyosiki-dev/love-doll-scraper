from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import re
from datetime import datetime, timedelta
from functools import lru_cache

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

CUP_ORDER = ['AA', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
PER_PAGE = 30  # 1ページあたりの表示件数

def get_db_connection():
    conn = sqlite3.connect('dolls.db')
    conn.row_factory = sqlite3.Row
    return conn

def extract_site_name(url):
    if not url:
        return ''
    domain = re.sub(r'^https?://(www\.)?', '', url)
    domain = domain.split('/')[0]
    return domain

# ★ インデックス作成（初回実行時のみ）
def create_indexes():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_id ON products(id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_specs_product_id ON specs(product_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_specs_key ON specs(spec_key)')
    # ★ 数値カラム用インデックス
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_height_cm ON products(height_cm)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_weight_kg ON products(weight_kg)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_foot_cm ON products(foot_cm)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_price_int ON products(price_int)')
    conn.commit()
    conn.close()

# 初回インデックス作成
create_indexes()

# ★ カテゴリ・材質リストをキャッシュ
@lru_cache(maxsize=1)
def get_all_categories():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ""')
    rows = [row['category'] for row in c.fetchall()]
    conn.close()
    return rows

@lru_cache(maxsize=1)
def get_all_materials():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT DISTINCT spec_value FROM specs WHERE spec_key = "材質" AND spec_value IS NOT NULL AND spec_value != ""')
    rows = [row['spec_value'] for row in c.fetchall()]
    conn.close()
    return rows

# --- ルート ---
@app.route('/')
def top():
    return render_template('top.html')

@app.route('/age-verify', methods=['POST'])
def age_verify():
    answer = request.form.get('age_confirm')
    if answer == 'yes':
        session['age_verified'] = True
        return redirect(url_for('search'))
    else:
        return render_template('age_denied.html')

@app.route('/legal')
def legal():
    return render_template('legal.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

# --- 検索（数値カラム対応版） ---
@app.route('/search', methods=['GET'])
def search():
    if not session.get('age_verified'):
        return redirect(url_for('top'))

    # フィルタパラメータ
    keyword = request.args.get('keyword', '').strip()
    height_min = request.args.get('height_min', '')
    height_max = request.args.get('height_max', '')
    weight_min = request.args.get('weight_min', '')
    weight_max = request.args.get('weight_max', '')
    foot_min = request.args.get('foot_min', '')
    foot_max = request.args.get('foot_max', '')
    price_min = request.args.get('price_min', '')
    price_max = request.args.get('price_max', '')
    selected_cups = request.args.getlist('cup')
    cup_m_or_more = request.args.get('cup_m_or_more') == 'on'
    categories = request.args.getlist('category')
    materials = request.args.getlist('material')
    sort_by = request.args.get('sort_by', 'price_asc')
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * PER_PAGE

    conn = get_db_connection()
    c = conn.cursor()

    # ★ メインクエリ（JOIN + GROUP BY、数値カラムを使用）
    query = '''
        SELECT 
            p.id, p.name, p.price, p.url, p.category,
            p.height_cm AS height,
            p.weight_kg AS weight,
            p.foot_cm AS foot,
            p.price_int AS price_int,
            MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) AS cup,
            MAX(CASE WHEN s.spec_key = 'バスト' THEN s.spec_value END) AS bust,
            MAX(CASE WHEN s.spec_key = 'アンダーバスト' THEN s.spec_value END) AS under_bust,
            MAX(CASE WHEN s.spec_key = 'ウエスト' THEN s.spec_value END) AS waist,
            MAX(CASE WHEN s.spec_key = 'ヒップ' THEN s.spec_value END) AS hip,
            MAX(CASE WHEN s.spec_key = '肩幅' THEN s.spec_value END) AS shoulder,
            MAX(CASE WHEN s.spec_key = '膣の深さ' THEN s.spec_value END) AS vagina_depth,
            MAX(CASE WHEN s.spec_key = 'アナルの深さ' THEN s.spec_value END) AS anal_depth,
            MAX(CASE WHEN s.spec_key = '口の深さ' THEN s.spec_value END) AS mouth_depth,
            MAX(CASE WHEN s.spec_key = '材質' THEN s.spec_value END) AS material
        FROM products p
        LEFT JOIN specs s ON p.id = s.product_id
        WHERE 1=1
    '''
    params = []

    # フィルタ条件（★ 数値カラムを直接参照）
    if keyword:
        query += ' AND p.name LIKE ?'
        params.append(f'%{keyword}%')
    if height_min:
        query += ' AND p.height_cm >= ?'
        params.append(float(height_min))
    if height_max:
        query += ' AND p.height_cm <= ?'
        params.append(float(height_max))
    if weight_min:
        query += ' AND p.weight_kg >= ?'
        params.append(float(weight_min))
    if weight_max:
        query += ' AND p.weight_kg <= ?'
        params.append(float(weight_max))
    if foot_min:
        query += ' AND p.foot_cm >= ?'
        params.append(float(foot_min))
    if foot_max:
        query += ' AND p.foot_cm <= ?'
        params.append(float(foot_max))
    if price_min:
        query += ' AND p.price_int >= ?'
        params.append(int(price_min))
    if price_max:
        query += ' AND p.price_int <= ?'
        params.append(int(price_max))
    if selected_cups:
        placeholders = ','.join(['?'] * len(selected_cups))
        query += f' AND MAX(CASE WHEN s.spec_key = "カップ数" THEN s.spec_value END) IN ({placeholders})'
        params.extend(selected_cups)
    if cup_m_or_more:
        query += '''
            AND MAX(CASE WHEN s.spec_key = "カップ数" THEN 
                CASE 
                    WHEN s.spec_value LIKE '%M%' THEN 13
                    WHEN s.spec_value LIKE '%N%' THEN 14
                    WHEN s.spec_value LIKE '%O%' THEN 15
                    WHEN s.spec_value LIKE '%P%' THEN 16
                    WHEN s.spec_value LIKE '%Q%' THEN 17
                    WHEN s.spec_value LIKE '%R%' THEN 18
                    WHEN s.spec_value LIKE '%S%' THEN 19
                    WHEN s.spec_value LIKE '%T%' THEN 20
                    WHEN s.spec_value LIKE '%U%' THEN 21
                    WHEN s.spec_value LIKE '%V%' THEN 22
                    WHEN s.spec_value LIKE '%W%' THEN 23
                    WHEN s.spec_value LIKE '%X%' THEN 24
                    WHEN s.spec_value LIKE '%Y%' THEN 25
                    WHEN s.spec_value LIKE '%Z%' THEN 26
                    WHEN s.spec_value LIKE '%G以上%' THEN 7
                    WHEN s.spec_value LIKE '%H%' THEN 8
                    WHEN s.spec_value LIKE '%I%' THEN 9
                    WHEN s.spec_value LIKE '%J%' THEN 10
                    WHEN s.spec_value LIKE '%K%' THEN 11
                    WHEN s.spec_value LIKE '%L%' THEN 12
                    WHEN s.spec_value LIKE '%F%' THEN 6
                    WHEN s.spec_value LIKE '%E%' THEN 5
                    WHEN s.spec_value LIKE '%D%' THEN 4
                    WHEN s.spec_value LIKE '%C%' THEN 3
                    WHEN s.spec_value LIKE '%B%' THEN 2
                    WHEN s.spec_value LIKE '%A%' THEN 1
                    WHEN s.spec_value LIKE '%AA%' THEN 0
                    ELSE 0
                END 
            END) >= 13
        '''
    if categories:
        placeholders = ','.join(['?'] * len(categories))
        query += f' AND p.category IN ({placeholders})'
        params.extend(categories)
    if materials:
        placeholders = ','.join(['?'] * len(materials))
        query += f' AND MAX(CASE WHEN s.spec_key = "材質" THEN s.spec_value END) IN ({placeholders})'
        params.extend(materials)

    query += ' GROUP BY p.id'

    # ★ ソート（数値カラムを使用）
    sort_map = {
        'price_asc': ('p.price_int ASC', 'price'),
        'price_desc': ('p.price_int DESC', 'price'),
        'height_asc': ('p.height_cm ASC', 'height'),
        'height_desc': ('p.height_cm DESC', 'height'),
        'weight_asc': ('p.weight_kg ASC', 'weight'),
        'weight_desc': ('p.weight_kg DESC', 'weight'),
        'bust_asc': ('MAX(CASE WHEN s.spec_key = "バスト" THEN CAST(REPLACE(s.spec_value, "cm", "") AS REAL) END) ASC', 'bust'),
        'bust_desc': ('MAX(CASE WHEN s.spec_key = "バスト" THEN CAST(REPLACE(s.spec_value, "cm", "") AS REAL) END) DESC', 'bust'),
    }
    if sort_by in sort_map:
        order_clause, _ = sort_map[sort_by]
        query += f' ORDER BY {order_clause}'
    else:
        query += ' ORDER BY p.id'

    # ★ ページネーション
    query += ' LIMIT ? OFFSET ?'
    params.extend([PER_PAGE, offset])

    c.execute(query, params)
    results = c.fetchall()
    conn.close()

    # サイト名を追加
    results_with_site = []
    for row in results:
        row_dict = dict(row)
        row_dict['site_name'] = extract_site_name(row['url'])
        results_with_site.append(row_dict)

    # 総件数取得（ページネーション用）
    conn2 = get_db_connection()
    total = conn2.execute('SELECT COUNT(*) AS total FROM products').fetchone()['total']
    conn2.close()

    # カテゴリ・材質リスト（キャッシュから）
    all_categories = get_all_categories()
    all_materials = get_all_materials()
    available_cups = CUP_ORDER

    # 範囲取得（数値カラムから直接取得）
    def get_min_max(col_name):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'SELECT MIN({col_name}) as min_val, MAX({col_name}) as max_val FROM products WHERE {col_name} IS NOT NULL')
        row = c.fetchone()
        conn.close()
        if row and row['min_val'] is not None:
            return int(row['min_val']), int(row['max_val'])
        return 0, 100

    def get_price_min_max():
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT MIN(price_int) as min_val, MAX(price_int) as max_val FROM products WHERE price_int IS NOT NULL')
        row = c.fetchone()
        conn.close()
        if row and row['min_val'] is not None:
            return int(row['min_val']), int(row['max_val'])
        return 0, 1000000

    price_min_val, price_max_val = get_price_min_max()
    height_min_val, height_max_val = get_min_max('height_cm')
    weight_min_val, weight_max_val = get_min_max('weight_kg')
    foot_min_val, foot_max_val = get_min_max('foot_cm')

    return render_template('search.html',
                           results=results_with_site,
                           keyword=keyword,
                           height_min=height_min,
                           height_max=height_max,
                           weight_min=weight_min,
                           weight_max=weight_max,
                           foot_min=foot_min,
                           foot_max=foot_max,
                           price_min=price_min,
                           price_max=price_max,
                           height_min_val=height_min_val,
                           height_max_val=height_max_val,
                           weight_min_val=weight_min_val,
                           weight_max_val=weight_max_val,
                           foot_min_val=foot_min_val,
                           foot_max_val=foot_max_val,
                           price_min_val=price_min_val,
                           price_max_val=price_max_val,
                           selected_cups=selected_cups,
                           cup_m_or_more=cup_m_or_more,
                           selected_categories=categories,
                           all_categories=all_categories,
                           selected_materials=materials,
                           all_materials=all_materials,
                           available_cups=available_cups,
                           sort_by=sort_by,
                           page=page,
                           total=total,
                           per_page=PER_PAGE)

# ExoClick検証ルート（既存）
@app.route('/012d8cfd3eec704c72e046dfd2b72ee0.html')
def verify_exoclick():
    return "012d8cfd3eec704c72e046dfd2b72ee0"

# WebAI ExoClick検証用ルート追加（love-doll-search用）
@app.route('/8823b79722a732180d4e970ca4900eb4.html')
def verify_exoclick_new():
    return "8823b79722a732180d4e970ca4900eb4"

if __name__ == '__main__':
    app.run(debug=True)