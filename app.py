from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from datetime import timedelta
import sqlite3
import re
import os
import hashlib
import time
from functools import lru_cache

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# ============================================================
# ★ セッション設定
# ============================================================
app.permanent_session_lifetime = timedelta(days=7)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('RENDER', 'false').lower() == 'true',
    SESSION_COOKIE_PATH='/',
)

# ============================================================
# ★ 簡易キャッシュ（メモリ内）
# ============================================================
_cache = {}
CACHE_EXPIRE = 60  # 秒

def get_cache_key(query, params):
    key_str = query + str(params)
    return hashlib.md5(key_str.encode()).hexdigest()

def get_cached(key):
    if key in _cache:
        data, timestamp = _cache[key]
        if time.time() - timestamp < CACHE_EXPIRE:
            return data
        else:
            del _cache[key]
    return None

def set_cached(key, data):
    _cache[key] = (data, time.time())

CUP_ORDER = ['AA', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
PER_PAGE = 30

YOURDOLL_REF = os.environ.get('YOURDOLL_REF', '')


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


_indexes_created = False

def ensure_indexes():
    global _indexes_created
    if _indexes_created:
        return
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
        _indexes_created = True
        print("✅ インデックス作成完了（遅延実行）")
    except Exception as e:
        print(f"⚠️ インデックス作成エラー: {e}")


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
    ensure_indexes()

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
    selected_cups = ','.join(sorted(request.args.getlist('cup')))
    cup_m_or_more = request.args.get('cup_m_or_more') == 'on'
    categories = ','.join(sorted(request.args.getlist('category')))
    materials = ','.join(sorted(request.args.getlist('material')))
    sort_by = request.args.get('sort_by', 'price_asc')
    page = request.args.get('page', 1, type=int)
    manufacturers = ','.join(sorted(request.args.getlist('manufacturer')))
    manufacturer_search = request.args.get('manufacturer_search', '').strip()
    site_name = request.args.get('site_name', '').strip()

    cache_key = f"{keyword}|{height_min}|{height_max}|{weight_min}|{weight_max}|{foot_min}|{foot_max}|{price_min}|{price_max}|{selected_cups}|{cup_m_or_more}|{categories}|{materials}|{sort_by}|{page}|{manufacturers}|{manufacturer_search}|{site_name}"
    cache_key = hashlib.md5(cache_key.encode()).hexdigest()

    cached_data = get_cached(cache_key)
    if cached_data is not None:
        results_with_site, total, price_min_val, price_max_val, height_min_val, height_max_val, weight_min_val, weight_max_val, foot_min_val, foot_max_val = cached_data
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
                               selected_cups=request.args.getlist('cup'),
                               cup_m_or_more=cup_m_or_more,
                               selected_categories=request.args.getlist('category'),
                               all_categories=get_all_categories(),
                               selected_materials=request.args.getlist('material'),
                               all_materials=get_all_materials(),
                               available_cups=CUP_ORDER,
                               sort_by=sort_by,
                               page=page,
                               total=total,
                               per_page=PER_PAGE)

    offset = (page - 1) * PER_PAGE
    conn = get_db_connection()
    c = conn.cursor()

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

    if keyword:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products_fts'")
        if c.fetchone():
            fts_keyword = ' AND '.join([f'"{w}"' for w in keyword.split()])
            c.execute("SELECT rowid FROM products_fts WHERE products_fts MATCH ? LIMIT 1000", (fts_keyword,))
            fts_ids = [row[0] for row in c.fetchall()]
            if fts_ids:
                placeholders = ','.join(['?'] * len(fts_ids))
                query += f' AND p.id IN ({placeholders})'
                params.extend(fts_ids)
            else:
                # ★ FTS5でヒットしなかった場合、LIKE検索にフォールバック（urlも含める）
                for word in keyword.split():
                    query += ' AND (p.name LIKE ? OR p.category LIKE ? OR p.manufacturer LIKE ? OR p.url LIKE ?)'
                    params.extend([f'%{word}%'] * 4)
        else:
            # FTS5が存在しない場合のフォールバック（urlも含める）
            for word in keyword.split():
                query += ' AND (p.name LIKE ? OR p.category LIKE ? OR p.manufacturer LIKE ? OR p.url LIKE ?)'
                params.extend([f'%{word}%'] * 4)

    if manufacturer_search:
        query += ' AND p.manufacturer LIKE ?'
        params.append(f'%{manufacturer_search}%')

    if site_name:
        query += ' AND p.url LIKE ?'
        params.append(f'%{site_name}%')

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
        cat_list = categories.split(',')
        placeholders = ','.join(['?'] * len(cat_list))
        query += f' AND p.category IN ({placeholders})'
        params.extend(cat_list)
    if manufacturers:
        mfg_list = manufacturers.split(',')
        placeholders = ','.join(['?'] * len(mfg_list))
        query += f' AND p.manufacturer IN ({placeholders})'
        params.extend(mfg_list)

    query += ' GROUP BY p.id'

    having_conditions = []
    if selected_cups:
        cup_list = selected_cups.split(',')
        placeholders = ','.join(['?'] * len(cup_list))
        having_conditions.append(f'MAX(CASE WHEN s.spec_key = "カップ数" THEN s.spec_value END) IN ({placeholders})')
        params.extend(cup_list)
    if cup_m_or_more:
        having_conditions.append('''
            CASE
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'AA' THEN 0
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'A' THEN 1
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'B' THEN 2
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'C' THEN 3
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'D' THEN 4
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'E' THEN 5
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'F' THEN 6
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'G' THEN 7
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'H' THEN 8
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'I' THEN 9
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'J' THEN 10
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'K' THEN 11
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'L' THEN 12
                WHEN MAX(CASE WHEN s.spec_key = 'カップ数' THEN s.spec_value END) = 'M以上' THEN 13
                ELSE 0
            END >= 13
        ''')
    if materials:
        mat_list = materials.split(',')
        placeholders = ','.join(['?'] * len(mat_list))
        having_conditions.append(f'MAX(CASE WHEN s.spec_key = "材質" THEN s.spec_value END) IN ({placeholders})')
        params.extend(mat_list)

    if having_conditions:
        query += ' HAVING ' + ' AND '.join(having_conditions)

    sort_map = {
        'price_asc': ('p.price_int ASC', 'price'),
        'price_desc': ('p.price_int DESC', 'price'),
        'height_asc': ('p.height_cm ASC', 'height'),
        'height_desc': ('p.height_cm DESC', 'height'),
        'weight_asc': ('p.weight_kg ASC', 'weight'),
        'weight_desc': ('p.weight_kg DESC', 'weight'),
        'bust_asc': ('MAX(CASE WHEN s.spec_key = "バスト" THEN CAST(REPLACE(s.spec_value, "cm", "") AS REAL) END) ASC', 'bust'),
        'bust_desc': ('MAX(CASE WHEN s.spec_key = "バスト" THEN CAST(REPLACE(s.spec_value, "cm", "") AS REAL) END) DESC', 'bust'),
        'cup_asc': ('MAX(CASE WHEN s.spec_key = "カップ数" THEN s.spec_value END) ASC', 'cup'),
        'cup_desc': ('MAX(CASE WHEN s.spec_key = "カップ数" THEN s.spec_value END) DESC', 'cup'),
    }
    if sort_by in sort_map:
        order_clause, _ = sort_map[sort_by]
        query += f' ORDER BY {order_clause}'
    else:
        query += ' ORDER BY p.id'

    count_query = re.sub(r'SELECT.*FROM products p', 'SELECT COUNT(DISTINCT p.id) AS total FROM products p', query)
    count_params = params[:len(params) - 2] if sort_by in sort_map else params[:]

    try:
        c.execute(count_query, count_params)
        total = c.fetchone()[0]
    except:
        total = 0

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

    cache_data = (results_with_site, total, price_min_val, price_max_val, height_min_val, height_max_val, weight_min_val, weight_max_val, foot_min_val, foot_max_val)
    set_cached(cache_key, cache_data)

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
                           selected_cups=request.args.getlist('cup'),
                           cup_m_or_more=cup_m_or_more,
                           selected_categories=request.args.getlist('category'),
                           all_categories=get_all_categories(),
                           selected_materials=request.args.getlist('material'),
                           all_materials=get_all_materials(),
                           available_cups=CUP_ORDER,
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