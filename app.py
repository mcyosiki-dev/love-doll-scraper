from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import re
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

CUP_ORDER = ['AA', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']

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

# --- トップページ（年齢確認） ---
@app.route('/')
def top():
    return render_template('top.html')

# --- 年齢確認処理 ---
@app.route('/age-verify', methods=['POST'])
def age_verify():
    answer = request.form.get('age_confirm')
    if answer == 'yes':
        session['age_verified'] = True
        return redirect(url_for('search'))
    else:
        return render_template('age_denied.html')

# --- 特定商取引法ページ ---
@app.route('/legal')
def legal():
    return render_template('legal.html')

# --- プライバシーポリシーページ ---
@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

# --- 検索ページ ---
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

    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        SELECT p.id, p.name, p.price, p.url, p.category,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '身長') AS height,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '体重') AS weight,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = 'カップ数') AS cup,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = 'バスト') AS bust,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = 'アンダーバスト') AS under_bust,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = 'ウエスト') AS waist,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = 'ヒップ') AS hip,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '肩幅') AS shoulder,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '足のサイズ') AS foot,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '膣の深さ') AS vagina_depth,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = 'アナルの深さ') AS anal_depth,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '口の深さ') AS mouth_depth,
               (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '材質') AS material
        FROM products p
        WHERE 1=1
    '''
    params = []

    if keyword:
        query += ' AND p.name LIKE ?'
        params.append(f'%{keyword}%')

    if height_min:
        query += ''' AND CAST(REPLACE(REPLACE(
                        (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '身長'), 'cm', ''), ' ', '') AS REAL) >= ?'''
        params.append(float(height_min))
    if height_max:
        query += ''' AND CAST(REPLACE(REPLACE(
                        (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '身長'), 'cm', ''), ' ', '') AS REAL) <= ?'''
        params.append(float(height_max))

    if weight_min:
        query += ''' AND CAST(REPLACE(REPLACE(
                        (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '体重'), 'kg', ''), ' ', '') AS REAL) >= ?'''
        params.append(float(weight_min))
    if weight_max:
        query += ''' AND CAST(REPLACE(REPLACE(
                        (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '体重'), 'kg', ''), ' ', '') AS REAL) <= ?'''
        params.append(float(weight_max))

    if foot_min:
        query += ''' AND CAST(REPLACE(REPLACE(
                        (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '足のサイズ'), 'cm', ''), ' ', '') AS REAL) >= ?'''
        params.append(float(foot_min))
    if foot_max:
        query += ''' AND CAST(REPLACE(REPLACE(
                        (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = '足のサイズ'), 'cm', ''), ' ', '') AS REAL) <= ?'''
        params.append(float(foot_max))

    if price_min:
        query += ' AND CAST(REPLACE(p.price, ",", "") AS INTEGER) >= ?'
        params.append(int(price_min))
    if price_max:
        query += ' AND CAST(REPLACE(p.price, ",", "") AS INTEGER) <= ?'
        params.append(int(price_max))

    if selected_cups:
        placeholders = ','.join(['?'] * len(selected_cups))
        query += f' AND (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = "カップ数") IN ({placeholders})'
        params.extend(selected_cups)

    if cup_m_or_more:
        query += '''
            AND EXISTS (
                SELECT 1 FROM specs s
                WHERE s.product_id = p.id
                AND s.spec_key = 'カップ数'
                AND (
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
                ) >= 13
            )
        '''

    if categories:
        placeholders = ','.join(['?'] * len(categories))
        query += f' AND p.category IN ({placeholders})'
        params.extend(categories)

    if materials:
        placeholders = ','.join(['?'] * len(materials))
        query += f' AND (SELECT spec_value FROM specs WHERE product_id = p.id AND spec_key = "材質") IN ({placeholders})'
        params.extend(materials)

    sort_map = {
        'price_asc': ('CAST(REPLACE(p.price, ",", "") AS INTEGER) ASC', 'price'),
        'price_desc': ('CAST(REPLACE(p.price, ",", "") AS INTEGER) DESC', 'price'),
        'height_asc': ('CAST(REPLACE(REPLACE(height, "cm", ""), " ", "") AS REAL) ASC', 'height'),
        'height_desc': ('CAST(REPLACE(REPLACE(height, "cm", ""), " ", "") AS REAL) DESC', 'height'),
        'weight_asc': ('CAST(REPLACE(REPLACE(weight, "kg", ""), " ", "") AS REAL) ASC', 'weight'),
        'weight_desc': ('CAST(REPLACE(REPLACE(weight, "kg", ""), " ", "") AS REAL) DESC', 'weight'),
        'bust_asc': ('CAST(REPLACE(REPLACE(bust, "cm", ""), " ", "") AS REAL) ASC', 'bust'),
        'bust_desc': ('CAST(REPLACE(REPLACE(bust, "cm", ""), " ", "") AS REAL) DESC', 'bust'),
    }
    if sort_by in sort_map:
        order_clause, _ = sort_map[sort_by]
        query += f' ORDER BY {order_clause}'
    else:
        query += ' ORDER BY p.id'

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    results_with_site = []
    for row in results:
        row_dict = dict(row)
        row_dict['site_name'] = extract_site_name(row['url'])
        results_with_site.append(row_dict)

    conn2 = get_db_connection()
    cursor2 = conn2.cursor()
    cursor2.execute('SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ""')
    all_categories = [row['category'] for row in cursor2.fetchall()]
    conn2.close()

    conn3 = get_db_connection()
    cursor3 = conn3.cursor()
    cursor3.execute('SELECT DISTINCT spec_value FROM specs WHERE spec_key = "材質" AND spec_value IS NOT NULL AND spec_value != ""')
    all_materials = [row['spec_value'] for row in cursor3.fetchall()]
    conn3.close()

    available_cups = CUP_ORDER

    def get_min_max(spec_key):
        conn5 = get_db_connection()
        cursor5 = conn5.cursor()
        cursor5.execute(f'''
            SELECT 
                MIN(CAST(REPLACE(REPLACE(spec_value, 'cm', ''), ' ', '') AS REAL)) as min_val,
                MAX(CAST(REPLACE(REPLACE(spec_value, 'cm', ''), ' ', '') AS REAL)) as max_val
            FROM specs
            WHERE spec_key = ? AND spec_value GLOB '*[0-9]*'
        ''', (spec_key,))
        row = cursor5.fetchone()
        conn5.close()
        if row and row['min_val'] is not None:
            return int(row['min_val']), int(row['max_val'])
        return 0, 100

    def get_price_min_max():
        conn6 = get_db_connection()
        cursor6 = conn6.cursor()
        cursor6.execute('SELECT MIN(CAST(REPLACE(price, ",", "") AS INTEGER)) as min_val, MAX(CAST(REPLACE(price, ",", "") AS INTEGER)) as max_val FROM products WHERE price IS NOT NULL AND price != "" AND price != "取得できず"')
        row = cursor6.fetchone()
        conn6.close()
        if row and row['min_val'] is not None:
            return int(row['min_val']), int(row['max_val'])
        return 0, 1000000

    price_min_val, price_max_val = get_price_min_max()

    height_min_val, height_max_val = get_min_max('身長')
    weight_min_val, weight_max_val = get_min_max('体重')
    foot_min_val, foot_max_val = get_min_max('足のサイズ')

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
                           sort_by=sort_by)

if __name__ == '__main__':
    app.run(debug=True)