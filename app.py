from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from datetime import timedelta
import sqlite3
import re
import os
from functools import lru_cache

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# ============================================================
# ★ セッション設定（ページネーションでセッションが失われる問題の修正）
# ============================================================
# セッション有効期限を7日に延長
app.permanent_session_lifetime = timedelta(days=7)

# セッションCookieの設定
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,  # JavaScriptからのアクセスを防止
    SESSION_COOKIE_SAMESITE='Lax',  # クロスサイトリクエストでもCookieを送信
    SESSION_COOKIE_SECURE=os.environ.get('RENDER', 'false').lower() == 'true',  # Render本番でのみSecureを有効
    SESSION_COOKIE_PATH='/',
)

CUP_ORDER = ['AA', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
PER_PAGE = 30

# ============================================================
# ★ アフィリエイト用環境変数
# ============================================================
YOURDOLL_REF = os.environ.get('YOURDOLL_REF', '')


# ============================================================
# ★ テンプレートで config.YOURDOLL_REF として参照可能にする
# ============================================================
@app.context_processor
def inject_config():
    return dict(config={
        'YOURDOLL_REF': YOURDOLL_REF,
    })


def get_db_connection():
    conn = sqlite3.connect('dolls.db')
    conn.row_factory = sqlite3.Row
    return conn


def extract_site_name(url):
    if not url:
        return ''
    domain = re.sub(r'^https?://(www\.)?', '', url)
    return domain.split('/')[0]


def create_indexes():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
        if not c.fetchone():
            conn.close()
            return
        c.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in c.fetchall()]
        if 'height_cm' in columns:
            c.execute('CREATE INDEX IF NOT EXISTS idx_products_height_cm ON products(height_cm)')
        if 'weight_kg' in columns:
            c.execute('CREATE INDEX IF NOT EXISTS idx_products_weight_kg ON products(weight_kg)')
        if 'foot_cm' in columns:
            c.execute('CREATE INDEX IF NOT EXISTS idx_products_foot_cm ON products(foot_cm)')
        if 'price_int' in columns:
            c.execute('CREATE INDEX IF NOT EXISTS idx_products_price_int ON products(price_int)')
        if 'site_name' in columns:
            c.execute('CREATE INDEX IF NOT EXISTS idx_products_site_name ON products(site_name)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_products_id ON products(id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_specs_product_id ON specs(product_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_specs_key ON specs(spec_key)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_specs_product_key ON specs(product_id, spec_key)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_specs_key_value ON specs(spec_key, spec_value)')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"インデックス作成エラー: {e}")


create_indexes()


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


@app.route('/')
def top():
    return render_template('top.html')


@app.route('/age-verify', methods=['POST'])
def age_verify():
    answer = request.form.get('age_confirm')
    if answer == 'yes':
        session['age_verified'] = True
        # ★ セッションを永続化（有効期限を延長）
        session.permanent = True
        return redirect(url_for('search'))
    else:
        return render_template('age_denied.html')


@app.route('/legal')
def legal():
    return render_template('legal.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/search', methods=['GET'])
def search():
    if not session.get('age_verified'):
        return redirect(url_for('top'))

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

    manufacturers = request.args.getlist('manufacturer')

    conn = get_db_connection()
    c = conn.cursor()

    # ★ 本修正：LEFT JOIN をサブクエリに変更
    query = '''
        SELECT
            p.id, p.name, p.price, p.url, p.category,
            p.height_cm AS height,
            p.weight_kg AS weight,
            p.foot_cm AS foot,
            p.price_int AS price_int,
            (SELECT MAX(spec_value) FROM specs WHERE product_id = p.id AND spec_key = 'カップ数') AS cup,
            (SELECT MAX(spec_value) FROM specs WHERE product_id = p.id AND spec_key = 'バスト') AS bust,
            (SELECT MAX(spec_value) FROM specs WHERE product_id = p.id AND spec_key = 'アンダーバスト') AS under_bust,
            (SELECT MAX(spec_value) FROM specs WHERE product_id = p.id AND spec_key = 'ウエスト') AS waist,
            (SELECT MAX(spec_value) FROM specs WHERE product_id = p.id AND spec_key = 'ヒップ') AS hip,
            (SELECT MAX(spec_value) FROM specs WHERE product_id = p.id AND spec_key = '肩幅') AS shoulder,
            (SELECT MAX(spec_value) FROM specs WHERE product_id = p.id AND spec_key = '膣の深さ') AS vagina_depth,
            (SELECT MAX(spec_value) FROM specs WHERE product_id = p.id AND spec_key = 'アナルの深さ') AS anal_depth,
            (SELECT MAX(spec_value) FROM specs WHERE product_id = p.id AND spec_key = '口の深さ') AS mouth_depth,
            (SELECT MAX(spec_value) FROM specs WHERE product_id = p.id AND spec_key = '材質') AS material
        FROM products p
        WHERE 1=1
    '''
    params = []

    # ★ キーワード検索（AND検索＋対象カラム拡張）
    if keyword:
        words = keyword.strip().split()
        for word in words:
            subquery = """
                (
                    p.name LIKE ?
                    OR p.category LIKE ?
                    OR p.manufacturer LIKE ?
                    OR EXISTS (
                        SELECT 1 FROM specs s2
                        WHERE s2.product_id = p.id
                        AND s2.spec_key = '材質'
                        AND s2.spec_value LIKE ?
                    )
                    OR EXISTS (
                        SELECT 1 FROM specs s2
                        WHERE s2.product_id = p.id
                        AND s2.spec_key = 'カップ数'
                        AND s2.spec_value LIKE ?
                    )
                )
            """
            params.extend([f'%{word}%'] * 5)
            query += f' AND {subquery}'

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
    if categories:
        placeholders = ','.join(['?'] * len(categories))
        query += f' AND p.category IN ({placeholders})'
        params.extend(categories)

    if manufacturers:
        placeholders = ','.join(['?'] * len(manufacturers))
        query += f' AND p.manufacturer IN ({placeholders})'
        params.extend(manufacturers)

    query += ' GROUP BY p.id'

    having_conditions = []

    if selected_cups:
        placeholders = ','.join(['?'] * len(selected_cups))
        having_conditions.append(f'cup IN ({placeholders})')
        params.extend(selected_cups)

    if cup_m_or_more:
        having_conditions.append('''
            CASE
                WHEN cup = 'AA' THEN 0
                WHEN cup = 'A' THEN 1
                WHEN cup = 'B' THEN 2
                WHEN cup = 'C' THEN 3
                WHEN cup = 'D' THEN 4
                WHEN cup = 'E' THEN 5
                WHEN cup = 'F' THEN 6
                WHEN cup = 'G' THEN 7
                WHEN cup = 'H' THEN 8
                WHEN cup = 'I' THEN 9
                WHEN cup = 'J' THEN 10
                WHEN cup = 'K' THEN 11
                WHEN cup = 'L' THEN 12
                WHEN cup = 'M以上' THEN 13
                ELSE 0
            END >= 13
        ''')

    if materials:
        placeholders = ','.join(['?'] * len(materials))
        having_conditions.append(f'material IN ({placeholders})')
        params.extend(materials)

    if having_conditions:
        query += ' HAVING ' + ' AND '.join(having_conditions)

    cup_order_case = '''
        CASE
            WHEN cup = 'AA' THEN 0
            WHEN cup = 'A' THEN 1
            WHEN cup = 'B' THEN 2
            WHEN cup = 'C' THEN 3
            WHEN cup = 'D' THEN 4
            WHEN cup = 'E' THEN 5
            WHEN cup = 'F' THEN 6
            WHEN cup = 'G' THEN 7
            WHEN cup = 'H' THEN 8
            WHEN cup = 'I' THEN 9
            WHEN cup = 'J' THEN 10
            WHEN cup = 'K' THEN 11
            WHEN cup = 'L' THEN 12
            WHEN cup = 'M以上' THEN 13
            ELSE 99
        END
    '''

    sort_map = {
        'price_asc': ('p.price_int ASC', 'price'),
        'price_desc': ('p.price_int DESC', 'price'),
        'height_asc': ('p.height_cm ASC', 'height'),
        'height_desc': ('p.height_cm DESC', 'height'),
        'weight_asc': ('p.weight_kg ASC', 'weight'),
        'weight_desc': ('p.weight_kg DESC', 'weight'),
        'bust_asc': ('CAST(REPLACE(bust, "cm", "") AS REAL) ASC', 'bust'),
        'bust_desc': ('CAST(REPLACE(bust, "cm", "") AS REAL) DESC', 'bust'),
        'cup_asc': (f'{cup_order_case} ASC', 'cup'),
        'cup_desc': (f'{cup_order_case} DESC', 'cup'),
    }
    if sort_by in sort_map:
        order_clause, _ = sort_map[sort_by]
        query += f' ORDER BY {order_clause}'
    else:
        query += ' ORDER BY p.id'

    query += ' LIMIT ? OFFSET ?'
    params.extend([PER_PAGE, offset])

    c.execute(query, params)
    results = c.fetchall()
    conn.close()

    results_with_site = []
    for row in results:
        row_dict = dict(row)
        row_dict['site_name'] = extract_site_name(row['url'])
        results_with_site.append(row_dict)

    conn2 = get_db_connection()
    total = conn2.execute('SELECT COUNT(*) AS total FROM products').fetchone()['total']
    conn2.close()

    all_categories = get_all_categories()
    all_materials = get_all_materials()
    available_cups = CUP_ORDER

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


@app.route('/012d8cfd3eec704c72e046dfd2b72ee0.html')
def verify_exoclick():
    return "012d8cfd3eec704c72e046dfd2b72ee0"


@app.route('/8823b79722a732180d4e970ca4900eb4.html')
def verify_exoclick_new():
    return "8823b79722a732180d4e970ca4900eb4"


@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml')


if __name__ == '__main__':
    app.run(debug=True)