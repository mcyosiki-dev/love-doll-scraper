# -*- coding: utf-8 -*-
import asyncio
import json
import re
import time
import sys
import os
import logging
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_DIR = Path(__file__).resolve().parent
EXCLUDED_BRANDS = {'ホーム', 'Home', '新品', '新着', 'キャンペーン', 'お買い得', '再販', '在庫', '限り', '特集', '送料', '期間', 'お', 'ご'}
TORSO_PATTERNS = [
    r'トルソー\s*型',
    r'トルソー\s*ラブドール',
    r'トルソー\s*タイプ',
    r'トルソー[（(]',
    r'半身\s*トルソー',
    r'トルソー$',
    r'トルソー',
]
TORSO_REGEX = re.compile('|'.join(TORSO_PATTERNS), re.IGNORECASE)

YOURDOLL_CATEGORY = "https://yourdoll.jp/product-category/all-sex-dolls/"
JPDOLL_CATEGORIES = []
KANADOLL_CATEGORY = "https://www.kanadoll.jp/?s=%E3%80%80&post_type=product"

DACHIWIFE_CATEGORIES = [
    "https://www.dachiwife.com/small-chest-love-dolls.html",
    "https://www.dachiwife.com/general-breast-real-dolls.html",
    "https://www.dachiwife.com/big-boobs-love-dolls.html",
    "https://www.dachiwife.com/super-breast-love-dolls.html",
]

MAX_PAGES_PER_CATEGORY = None
if os.environ.get('MAX_PAGES_PER_CATEGORY'):
    try:
        MAX_PAGES_PER_CATEGORY = int(os.environ.get('MAX_PAGES_PER_CATEGORY'))
        print(f"ℹ️ 最大ページ数制限: {MAX_PAGES_PER_CATEGORY} ページに設定されました")
    except ValueError:
        pass

SCRAPE_TARGET = os.environ.get('SCRAPE_TARGET', 'all')

OUTPUT_FILE = BASE_DIR / 'all_data.json'
ERROR_FILE = BASE_DIR / 'error.log'

MAX_NAV_WAIT = 45000
FAST_WAIT_MS = 250


def normalize_spec_key(key):
    key = key.strip()
    if re.search(r'高さ', key):
        return "身長"
    if re.search(r'重さ', key):
        return "体重"
    mapping = {
        "トップ": "バスト",
        "バスト": "バスト",
        "アンダー": "アンダーバスト",
        "アンダーバスト": "アンダーバスト",
        "膣深さ": "膣の深さ",
        "肛門深さ": "アナルの深さ",
        "口深さ": "口の深さ",
        "足サイズ": "足のサイズ",
        "素材": "材質",
        "Silicon": "シリコン",
        "silicon": "シリコン",
        "シリコーン": "シリコン",
        "シリコン＋TPE": "シリコン/TPE",
        "シリコン＆TPE": "シリコン/TPE",
        "シリコン+TPE": "シリコン/TPE",
        "シリコン&TPE": "シリコン/TPE",
        "カップ": "カップ数",
        "Cup": "カップ数",
        "cup": "カップ数",
    }
    for old, new in mapping.items():
        if old in key:
            return new
    return key


def clean_spec_value(value):
    cleaned = re.sub(r'\([^)]*\)', '', value)
    return cleaned.strip() if cleaned else value


def clean_height(value):
    match = re.search(r'(\d+)\s*[A-Za-z]*\s*(cm)', value, re.IGNORECASE)
    if match:
        return match.group(1) + match.group(2)
    match_num = re.search(r'(\d+)', value)
    if match_num:
        return match_num.group(1) + "cm"
    return value


def calculate_cup(top_bust, under_bust):
    if not top_bust or not under_bust:
        return None
    try:
        def extract_num(val):
            match = re.search(r'([\d.]+(?:\-[\d.]+)?)', str(val))
            return match.group(1) if match else None
        top_num = extract_num(top_bust)
        under_num = extract_num(under_bust)
        if not top_num or not under_num:
            return None
        def avg_range(val):
            if '-' in val:
                parts = val.split('-')
                return (float(parts[0]) + float(parts[1])) / 2
            return float(val)
        diff = avg_range(top_num) - avg_range(under_num)
    except:
        return None
    if diff < 10: return "AA"
    elif diff < 12.5: return "A"
    elif diff < 15: return "B"
    elif diff < 17.5: return "C"
    elif diff < 20: return "D"
    elif diff < 22.5: return "E"
    elif diff < 25: return "F"
    elif diff < 27.5: return "G"
    elif diff < 30: return "H"
    elif diff < 32.5: return "I"
    elif diff < 35: return "J"
    elif diff < 37.5: return "K"
    elif diff < 40: return "L"
    else: return "M以上"


def is_unwanted(product_name, html_text, url=None):
    if url and ('homecoming' in url or '里帰り' in url):
        logging.info(f"スキップ（URL）: {url}")
        return True
    if "里帰り" in product_name or "受付専用" in product_name:
        logging.info(f"スキップ（商品名）: {product_name}")
        return True
    for kw in ["福袋", "ランダムセット", "ヘッド単体", "ヘッド単品", "ボディ単体", "頭部単体", "頭部単品"]:
        if kw in product_name:
            logging.info(f"スキップ（除外キーワード: {kw}）: {product_name}")
            return True
    return False


def get_main_text(soup):
    for selector in [
        '.woocommerce-product-details__short-description',
        '.product-short-description',
        'div#tab-description',
        '.product-info-summary',
        '.summary.entry-summary',
    ]:
        elem = soup.select_one(selector)
        if elem:
            return elem.get_text(separator=' ', strip=True)
    product_div = soup.find('div', class_='product')
    if product_div:
        for unwanted in product_div.select('.reviews_tab, .related, .upsells, .wd-social-icons'):
            unwanted.decompose()
        return product_div.get_text(separator=' ', strip=True)[:3000]
    return ''


def determine_type(product_name, spec, html_text, soup):
    main_text = get_main_text(soup)
    text = product_name + " " + main_text
    if "オナホール" in text:
        return "オナホール"
    if TORSO_REGEX.search(text):
        return "トルソー"
    if any(kw in text for kw in ["男性", "メンズ", "Male"]) and "バスト" not in spec:
        return "男性型"
    if "バスト" in spec or "身長" in spec:
        return "女性型"
    if any(kw in product_name for kw in ["女性", "レディ", "ガール", "ラブドール"]):
        return "女性型"
    return "不明"


def extract_site_name(url):
    if not url:
        return ''
    domain = re.sub(r'^https?://(www\.)?', '', url)
    return domain.split('/')[0]


def load_processed_urls():
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {item['商品URL'] for item in data if isinstance(item, dict) and item.get('商品URL')}
    except:
        return set()


def log_error(url, msg):
    with open(ERROR_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {url} | {msg}\n")


def extract_price(text):
    if not text:
        return "取得できず"
    discount_match = re.search(r'(\d+)\s*[%％]\s*(?:OFF|オフ|割引)', text, re.IGNORECASE)
    discount_rate = None
    if discount_match:
        discount_rate = int(discount_match.group(1)) / 100
    numbers = re.findall(r'([\d,]+)', text)
    if not numbers:
        return "取得できず"
    int_numbers = [int(n.replace(',', '')) for n in numbers]
    if discount_rate is not None and len(int_numbers) >= 1:
        final_price = int_numbers[-1]
        if 0 < discount_rate < 1:
            original_price = final_price / (1 - discount_rate)
            return str(int(round(original_price)))
        return str(final_price)
    return str(int_numbers[0])


def extract_height_cup_from_title(title):
    if not title:
        return None, None
    match = re.search(r'(\d+)\s*cm\s*([A-Z])\s*カップ', title, re.IGNORECASE)
    if match:
        return match.group(1) + 'cm', match.group(2).upper()
    return None, None


def extract_brand_from_name(product_name):
    cleaned = re.sub(r'[【\[（(][^】\]）)]*[】\]）)]', '', product_name).strip()
    match = re.match(r'^([A-Za-z]+(?:\s+[A-Za-z]+)?)', cleaned)
    if match:
        return match.group(1)
    match = re.match(r'^([A-Za-z]+|[一-龥]+)', cleaned)
    if match:
        return match.group(1)
    return ''


def extract_metadata(soup, url, product_name):
    metadata = {}
    if 'angeldoll.jp' in url:
        brand_patterns = [
            'Aotume Doll', 'WM Doll', 'Sino Doll', 'Art Doll',
            'AXB Doll', 'MOZU DOLL', 'JYDOLL', '羊角社',
            'ElsaBabe', 'BC DOLL', '蛍火日記', 'RZR Doll',
            'Fanreal', 'FUDOLL', 'Irontech', 'Jiusheng',
            'Sanhui', 'WMdoll', 'XTDOLL', 'XYdoll'
        ]
        for pattern in brand_patterns:
            if re.search(pattern, product_name, re.IGNORECASE):
                metadata['manufacturer'] = pattern
                break
    if 'manufacturer' not in metadata:
        brand = extract_brand_from_name(product_name)
        if brand and brand not in EXCLUDED_BRANDS:
            metadata['manufacturer'] = brand
        else:
            breadcrumb = soup.select_one('nav.woocommerce-breadcrumb')
            if breadcrumb:
                parts = breadcrumb.get_text(separator='|').split('|')
                if len(parts) >= 2:
                    candidate = parts[-2].strip()
                    if candidate not in EXCLUDED_BRANDS:
                        metadata['manufacturer'] = candidate
            if 'manufacturer' not in metadata:
                h1 = soup.find('h1', class_='product-title')
                if h1:
                    brand = extract_brand_from_name(h1.get_text(strip=True))
                    if brand and brand not in EXCLUDED_BRANDS:
                        metadata['manufacturer'] = brand
    if 'manufacturer' not in metadata:
        metadata['manufacturer'] = None

    match = re.search(r'/product[s]?/(\d+)/?', url)
    metadata['site_product_id'] = match.group(1) if match else ''
    return metadata


def generate_variant_name(base_name, variant, index):
    parts = [base_name]
    for key in ['身長', 'カップ数', '体重', 'バスト', 'ヒップ']:
        val = variant.get(key)
        if val:
            parts.append(str(val))
    if len(parts) == 1:
        parts.append(f"バリエーション{index+1}")
    return " ".join(parts)


async def prepare_page(page):
    await page.set_extra_http_headers({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    })

    async def route_handler(route):
        if route.request.resource_type in ('image', 'media', 'font'):
            await route.abort()
        else:
            await route.continue_()

    await page.route('**/*', route_handler)


async def scrape_one(page, url, processed_urls, max_retries=3):
    if url in processed_urls:
        return None

    print(f"  処理中: {url}")
    html = None
    wait_until = 'networkidle' if 'yourdoll.jp' in url else 'domcontentloaded'

    for attempt in range(max_retries):
        try:
            response = await page.goto(url, timeout=MAX_NAV_WAIT, wait_until=wait_until)
            if response and response.status == 404:
                if attempt == max_retries - 1:
                    log_error(url, "HTTP 404")
                    return None
                await asyncio.sleep(1.5 * (attempt + 1))
                continue

            for selector in [
                'button:has-text("はい")',
                'a:has-text("はい")',
                'text="はい"',
                '#agy-accept',
                '._ymcart_popup_close_button',
                '.restriction-btn.restriction-confirm',
                '.age_btn:first-child',
            ]:
                try:
                    await page.click(selector, timeout=2000)
                    break
                except:
                    pass

            await page.wait_for_timeout(FAST_WAIT_MS)
            html = await page.content()
            break
        except Exception as e:
            log_error(url, f"試行 {attempt+1} エラー: {e}")
            if attempt == max_retries - 1:
                return None
            await asyncio.sleep(1.5 * (attempt + 1))

    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    html_text = soup.get_text()
    name_tag = soup.find('h1', class_='product-title') or soup.find('h1')
    product_name = name_tag.text.strip() if name_tag else "不明"

    meta = extract_metadata(soup, url, product_name)
    manufacturer = meta.get('manufacturer')
    site_product_id = meta.get('site_product_id')
    print(f"    🏷️ メーカー: {manufacturer}")
    print(f"    🔖 商品ID: {site_product_id}")

    if is_unwanted(product_name, html_text, url):
        print(f"  ⏭️ スキップ（不要データ）: {product_name}")
        return None

    price = "取得できず"
    price_elem = soup.find('div', class_='price') or soup.find('p', class_='price')
    if price_elem:
        price = extract_price(price_elem.get_text(strip=True))
    if price == "取得できず":
        for text in soup.stripped_strings:
            if '円' in text and len(text) < 50:
                price = extract_price(text)
                if price != "取得できず":
                    break

    all_specs = []
    penis = []

    for table in soup.find_all('table'):
        table_html = str(table)
        if "最小/最大直径" in table_html or "シリアルナンバー" in table_html:
            rows = table.find_all('tr')
            if rows:
                headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
                for row in rows[1:]:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) < 3:
                        continue
                    row_data = {}
                    for idx, h in enumerate(headers):
                        if idx < len(cols):
                            row_data[h] = cols[idx].get_text(strip=True)
                    if row_data:
                        penis.append(row_data)
            break

    panels = soup.find_all('div', class_='vc_tta-panel')
    if panels:
        for panel in panels:
            title_elem = panel.find('h4', class_='vc_tta-panel-title')
            if not title_elem:
                continue
            title_text = title_elem.get_text(strip=True)
            height_match = re.search(r'(\d+)cm', title_text)
            height = height_match.group(1) + 'cm' if height_match else ''

            table = panel.find('table')
            if not table:
                continue

            current_spec = {}
            for row in table.find_all('tr'):
                cols = row.find_all(['td', 'th'])
                if len(cols) < 4:
                    continue
                k1, v1 = cols[0].get_text(strip=True), cols[1].get_text(strip=True)
                k2, v2 = cols[2].get_text(strip=True), cols[3].get_text(strip=True)
                if k1 and v1:
                    nk = normalize_spec_key(k1)
                    current_spec[nk] = clean_height(v1) if nk == "身長" else clean_spec_value(v1)
                if k2 and v2:
                    nk = normalize_spec_key(k2)
                    current_spec[nk] = clean_height(v2) if nk == "身長" else clean_spec_value(v2)

            if current_spec:
                if height and '身長' not in current_spec:
                    current_spec['身長'] = height
                if 'バスト' in current_spec and 'アンダーバスト' in current_spec:
                    cup = calculate_cup(current_spec['バスト'], current_spec['アンダーバスト'])
                    if cup:
                        current_spec['カップ数'] = cup
                if penis:
                    current_spec['ペニス'] = penis
                all_specs.append(current_spec)
    else:
        for table in soup.find_all('table'):
            table_html = str(table)
            if "最小/最大直径" in table_html or "シリアルナンバー" in table_html:
                continue
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
            current_spec = {}
            for row in rows:
                cols = row.find_all(['td', 'th'])
                if len(cols) < 2:
                    continue
                if len(cols) == 2:
                    k = cols[0].get_text(strip=True)
                    v = cols[1].get_text(strip=True)
                    if k and v:
                        nk = normalize_spec_key(k)
                        current_spec[nk] = clean_height(v) if nk == "身長" else clean_spec_value(v)
                elif len(cols) >= 4:
                    k1, v1 = cols[0].get_text(strip=True), cols[1].get_text(strip=True)
                    k2, v2 = cols[2].get_text(strip=True), cols[3].get_text(strip=True)
                    if k1 and v1:
                        nk = normalize_spec_key(k1)
                        current_spec[nk] = clean_height(v1) if nk == "身長" else clean_spec_value(v1)
                    if k2 and v2:
                        nk = normalize_spec_key(k2)
                        current_spec[nk] = clean_height(v2) if nk == "身長" else clean_spec_value(v2)
            if current_spec and (set(current_spec.keys()) & {"身長", "体重", "バスト", "ウエスト", "ヒップ", "材質", "カップ数"}):
                if penis:
                    current_spec['ペニス'] = penis
                all_specs.append(current_spec)

    title_height, title_cup = extract_height_cup_from_title(product_name)
    if not all_specs:
        current_spec = {}
        for kw in ["素材", "重さ", "高さ", "幅", "長さ", "タイプ", "膣の深さ", "肛門の深さ", "梱包サイズ", "身長", "体重", "バスト", "ウエスト", "ヒップ"]:
            m = re.search(rf'{kw}[：:]\s*([^\n]+)', html_text)
            if m:
                nk = normalize_spec_key(kw)
                current_spec[nk] = clean_height(m.group(1)) if nk == "身長" else clean_spec_value(m.group(1))
        if current_spec:
            if penis:
                current_spec['ペニス'] = penis
            all_specs.append(current_spec)

    if not all_specs:
        current_spec = {}
        if title_height:
            current_spec["身長"] = title_height
        if title_cup:
            current_spec["カップ数"] = title_cup
        if current_spec:
            all_specs.append(current_spec)

    for variant in all_specs:
        variant["大分類"] = determine_type(product_name, variant, html_text, soup)
        variant["サイト名"] = extract_site_name(url)

    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = []

    changed = False
    if all_specs:
        for idx, variant in enumerate(all_specs):
            variant_name = generate_variant_name(product_name, variant, idx)
            data.append({
                "商品名": variant_name,
                "価格": price,
                "商品URL": url,
                "manufacturer": manufacturer,
                "site_product_id": site_product_id,
                "スペックバリエーション": [variant]
            })
            print(f"  ✅ 保存完了（バリエーション）: {variant_name[:30]}...")
            changed = True
    else:
        spec = {"大分類": determine_type(product_name, {}, html_text, soup), "サイト名": extract_site_name(url)}
        data.append({
            "商品名": product_name,
            "価格": price,
            "商品URL": url,
            "manufacturer": manufacturer,
            "site_product_id": site_product_id,
            "スペックバリエーション": [spec]
        })
        print(f"  ✅ 保存完了（フォールバック）: {product_name[:30]}...")
        changed = True

    if changed:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    processed_urls.add(url)
    return True


# ============================================================
# ★ AngelDoll 用 URL収集関数（新規追加）
# ============================================================
async def collect_urls_angeldoll(max_pages=None):
    """AngelDoll の商品URLを収集（カテゴリ一覧 → 各カテゴリ → 商品一覧）"""
    collected = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await prepare_page(page)

        category_url = "https://www.angeldoll.jp/product-category/all/"
        print(f"  🔍 AngelDoll カテゴリ一覧を取得中: {category_url}")

        try:
            await page.goto(category_url, timeout=60000, wait_until='domcontentloaded')
            await page.wait_for_timeout(2000)
            html = await page.content()
        except Exception as e:
            print(f"    ⚠️ カテゴリ一覧取得失敗: {e}")
            await browser.close()
            return collected

        soup = BeautifulSoup(html, 'html.parser')
        category_links = soup.select('ul.product-categories a')
        if not category_links:
            category_links = soup.select('a[href*="/product-category/"]')

        print(f"  🔍 {len(category_links)} 件のカテゴリを検出")

        for cat_link in category_links:
            cat_href = cat_link.get('href')
            if not cat_href or '/product-category/all/' in cat_href:
                continue
            if not cat_href.startswith('http'):
                cat_href = 'https://www.angeldoll.jp' + cat_href

            print(f"    📂 カテゴリ: {cat_link.get_text(strip=True)}")

            page_num = 1
            while True:
                if page_num == 1:
                    url = cat_href
                else:
                    url = cat_href.rstrip('/') + f'/page/{page_num}/'

                try:
                    await page.goto(url, timeout=60000, wait_until='domcontentloaded')
                    await page.wait_for_timeout(1500)
                    html = await page.content()
                except Exception as e:
                    print(f"      ⚠️ ページ {page_num} 読み込み失敗: {e}")
                    break

                soup = BeautifulSoup(html, 'html.parser')
                product_links = soup.select('ul.products li.product a')
                if not product_links:
                    product_links = soup.select('a[href*="/product/"]')

                found = False
                for a in product_links:
                    href = a.get('href')
                    if href and '/product/' in href and '/product-category/' not in href:
                        full_url = href if href.startswith('http') else 'https://www.angeldoll.jp' + href
                        full_url = re.sub(r'\?.*$', '', full_url)
                        collected.add(full_url)
                        found = True

                if not found:
                    break

                next_link = soup.select_one('a.next.page-numbers')
                if not next_link:
                    break
                page_num += 1
                if max_pages and page_num > max_pages:
                    print(f"      ⏹️ 最大ページ数 {max_pages} に達したため終了")
                    break

        await browser.close()
    return collected


# ============================================================
# 既存の URL収集関数（YourDoll, Kanadoll, Dachiwife）
# ============================================================
async def collect_urls_yourdoll(max_pages=None):
    collected = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page_num = 1
        while True:
            url = YOURDOLL_CATEGORY if page_num == 1 else f"{YOURDOLL_CATEGORY}page/{page_num}/"
            print(f"  🔍 yourdoll ページ {page_num} をクロール中: {url}")
            try:
                await page.goto(url, timeout=60000, wait_until='networkidle')
                await page.wait_for_timeout(2000)
                html = await page.content()
            except Exception as e:
                print(f"    ⚠️ ページ読み込み失敗（終了）: {e}")
                break
            soup = BeautifulSoup(html, 'html.parser')
            found = False
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/product/' in href and '/product-category/' not in href:
                    full = "https://yourdoll.jp" + href if href.startswith('/') else href
                    full = re.sub(r'\?.*$', '', full)
                    collected.add(full)
                    found = True
            if not found:
                print(f"    ⏹️ 商品リンクが見つからなかったため終了")
                break
            next_link = soup.find('a', class_='next')
            if not next_link:
                print(f"    ⏹️ 次へボタンがないため終了")
                break
            page_num += 1
            if max_pages and page_num > max_pages:
                print(f"    ⏹️ 最大ページ数 {max_pages} に達したため終了")
                break
        await browser.close()
    return collected


async def collect_urls_jpdolls(max_pages=None):
    return set()


async def collect_urls_kanadoll(max_pages=None):
    collected = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page_num = 1
        base_url = KANADOLL_CATEGORY
        while True:
            url = base_url if page_num == 1 else f"{base_url}&page={page_num}"
            print(f"  🔍 kanadoll ページ {page_num} をクロール中: {url}")
            try:
                await page.goto(url, timeout=60000, wait_until='domcontentloaded')
                try:
                    await page.click('#agy-accept', timeout=3000)
                except:
                    try:
                        await page.click('button:has-text("はい")', timeout=3000)
                    except:
                        try:
                            await page.click('text="はい"', timeout=3000)
                        except:
                            pass
                await page.wait_for_timeout(2000)
                html = await page.content()
            except Exception as e:
                print(f"    ⚠️ ページ読み込み失敗（終了）: {e}")
                break
            soup = BeautifulSoup(html, 'html.parser')
            product_links = soup.select('ul.products li.product a')
            if not product_links:
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/product/' in href and not href.startswith('https://www.kanadoll.jp/?s='):
                        full = href if href.startswith('http') else "https://www.kanadoll.jp" + href
                        full = re.sub(r'\?.*$', '', full)
                        collected.add(full)
                if not collected:
                    print(f"    ⏹️ 商品リンクが見つからなかったため終了")
                    break
            else:
                for a in product_links:
                    href = a.get('href')
                    if href and '/product/' in href:
                        full = href if href.startswith('http') else "https://www.kanadoll.jp" + href
                        full = re.sub(r'\?.*$', '', full)
                        collected.add(full)
            next_link = soup.find('a', class_='next')
            if not next_link:
                print(f"    ⏹️ 次へボタンがないため終了")
                break
            page_num += 1
            if max_pages and page_num > max_pages:
                print(f"    ⏹️ 最大ページ数 {max_pages} に達したため終了")
                break
        await browser.close()
    return collected


async def collect_urls_dachiwife(category_urls, max_pages=None):
    collected = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        base_domain = "https://www.dachiwife.com"
        for cat_url in category_urls:
            page_num = 1
            base_name = cat_url.split('/')[-1].replace('.html', '')
            while True:
                url = cat_url if page_num == 1 else f"{base_domain}/{base_name}-{page_num}.html"
                print(f"  🔍 dachiwife ({base_name}) ページ {page_num} をクロール中: {url}")
                try:
                    await page.goto(url, timeout=60000, wait_until='domcontentloaded')
                    try:
                        await page.click('.restriction-btn.restriction-confirm', timeout=5000)
                    except:
                        pass
                    try:
                        await page.wait_for_selector('div.product-block', timeout=15000)
                    except:
                        pass
                    await page.wait_for_timeout(3000)
                    html = await page.content()
                except Exception as e:
                    print(f"    ⚠️ ページ読み込み失敗（終了）: {e}")
                    break
                soup = BeautifulSoup(html, 'html.parser')
                found = False
                for a in soup.select('div.product-block a'):
                    href = a.get('href')
                    if href and href.endswith('.html'):
                        full_url = href if href.startswith('http') else base_domain + href
                        full_url = re.sub(r'\?.*$', '', full_url)
                        collected.add(full_url)
                        found = True
                if not found:
                    print(f"    ⏹️ 商品リンクが見つからなかったため終了")
                    break
                pagination = soup.find('ul', class_='pagination')
                next_link = None
                if pagination:
                    for li in pagination.find_all('li', class_='page-item'):
                        a = li.find('a', class_='page-link')
                        if a and a.get_text(strip=True) == '»':
                            next_link = a
                            break
                if not next_link:
                    print(f"    ⏹️ 次へボタンがないため終了")
                    break
                page_num += 1
                if max_pages and page_num > max_pages:
                    print(f"    ⏹️ 最大ページ数 {max_pages} に達したため終了")
                    break
        await browser.close()
    return collected


# ============================================================
# メイン関数
# ============================================================
async def main():
    start_time = time.time()
    print("=" * 60)
    print(f"🚀 一括スクレイピングを開始します（対象: {SCRAPE_TARGET}）")
    print(f"🕒 開始時刻: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n📡 ステップ1: 商品URLを収集します...")
    all_urls = set()

    if SCRAPE_TARGET in ('all', 'yourdoll'):
        print("\n  [yourdoll]")
        yd_urls = await collect_urls_yourdoll(max_pages=MAX_PAGES_PER_CATEGORY)
        print(f"  ✅ yourdoll: {len(yd_urls)} 件のURLを収集")
        all_urls.update(yd_urls)

    if SCRAPE_TARGET in ('all', 'angeldoll'):
        print("\n  [angeldoll]")
        ad_urls = await collect_urls_angeldoll(max_pages=MAX_PAGES_PER_CATEGORY)
        print(f"  ✅ angeldoll: {len(ad_urls)} 件のURLを収集")
        all_urls.update(ad_urls)

    if SCRAPE_TARGET in ('all', 'kanadoll'):
        print("\n  [kanadoll]")
        kd_urls = await collect_urls_kanadoll(max_pages=MAX_PAGES_PER_CATEGORY)
        print(f"  ✅ kanadoll: {len(kd_urls)} 件のURLを収集")
        all_urls.update(kd_urls)

    if SCRAPE_TARGET in ('all', 'dachiwife'):
        print("\n  [dachiwife]")
        dw_urls = await collect_urls_dachiwife(DACHIWIFE_CATEGORIES, max_pages=MAX_PAGES_PER_CATEGORY)
        print(f"  ✅ dachiwife: {len(dw_urls)} 件のURLを収集")
        all_urls.update(dw_urls)

    print(f"\n📊 合計 {len(all_urls)} 件のURLを収集しました。")

    print("\n📋 ステップ2: 未処理のURLをフィルタリングします...")
    processed = load_processed_urls()
    new_urls = [url for url in all_urls if url not in processed]
    print(f"📊 既処理: {len(processed)} 件, 新規: {len(new_urls)} 件")

    if not new_urls:
        print("✅ 新規URLはありません。処理を終了します。")
        return

    print("\n🔄 ステップ3: スクレイピングを実行します...")
    success_count = 0
    error_count = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await prepare_page(page)
        try:
            for i, url in enumerate(new_urls, 1):
                print(f"\n--- {i}/{len(new_urls)} ---")
                result = await scrape_one(page, url, processed)
                if result:
                    success_count += 1
                else:
                    error_count += 1
                await asyncio.sleep(1.5)
        finally:
            await browser.close()

    print("\n💾 ステップ4: データベースを更新します...")
    import subprocess
    try:
        subprocess.run([sys.executable, "json_to_db.py"], check=True, capture_output=False)
        print("✅ データベース更新完了")
    except Exception as e:
        print(f"⚠️ データベース更新中にエラー: {e}")

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"✅ 一括スクレイピングが完了しました！")
    print(f"📊 処理結果: 成功 {success_count} 件, エラー {error_count} 件")
    print(f"🕒 経過時間: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())