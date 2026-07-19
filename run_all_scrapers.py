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


# ============================================================
# SITE_CONFIGS（全サイト）
# ============================================================
SITE_CONFIGS = {
    "dolltime": {
        "base_url": "https://www.dolltime.jp/Search-%E3%83%89%E3%83%BC%E3%83%AB/list-r{page}.html",
        "page_pattern": "list-r{page}.html",
        "link_selector": "a[href*='/product-p']",
        "link_pattern": "/product-p",
        "domain": "https://www.dolltime.jp",
        "age_selectors": []
    },
    "bijindoll": {
        "base_url": "https://www.bijindoll.com/Search-%E3%83%89%E3%83%BC%E3%83%AB/list-r{page}.html",
        "page_pattern": "list-r{page}.html",
        "link_selector": "a[href*='/product-p']",
        "link_pattern": "/product-p",
        "domain": "https://www.bijindoll.com",
        "age_selectors": [
            "._ymcart_popup_close_button",
            'button:has-text("はい")',
            'a:has-text("はい")',
            'text="はい"'
        ]
    },
    "ramondoll": {
        "base_url": "https://www.ramondoll.com/Search-%E3%83%89%E3%83%BC%E3%83%AB/list-r{page}.html",
        "page_pattern": "list-r{page}.html",
        "link_selector": "a[href*='/product-p']",
        "link_pattern": "/product-p",
        "domain": "https://www.ramondoll.com",
        "age_selectors": [
            "._ymcart_popup_close_button",
            'button:has-text("はい")',
            'a:has-text("はい")',
            'text="はい"'
        ]
    },
    "rakuendoll": {
        "base_url": "https://www.rakuendoll.jp/Recommend-rc254887-{page}.html",
        "page_pattern": "-{page}.html",
        "link_selector": "div.product_item a.pic",
        "link_pattern": "/product-p",
        "domain": "https://www.rakuendoll.jp",
        "age_selectors": [
            "._ymcart_popup_close_button",
            'button:has-text("はい")',
            'a:has-text("はい")',
            'text="はい"'
        ]
    },
    "oldoll": {
        "base_url": "https://www.oldoll.com/Recommend-rc24867-{page}.html",
        "page_pattern": "-{page}.html",
        "link_selector": "a[href*='/product-p']",
        "link_pattern": "/product-p",
        "domain": "https://www.oldoll.com",
        "age_selectors": [
            "._ymcart_popup_close_button",
            'button:has-text("はい")',
            'a:has-text("はい")',
            'text="はい"'
        ]
    },
    "yourdoll": {
        "base_url": "https://yourdoll.jp/shop/?page={page}&per_page=100",
        "page_pattern": "page={page}",
        "link_selector": "a[href*='/product/']",
        "link_pattern": "/product/",
        "domain": "https://yourdoll.jp",
        "age_selectors": [
            'button:has-text("はい")',
            'a:has-text("はい")',
            'text="はい"',
            '#agy-accept',
            '._ymcart_popup_close_button'
        ]
    },
    "kanadoll": {
        "base_url": "https://www.kanadoll.jp/shop/?page={page}",
        "page_pattern": "page={page}",
        "link_selector": "a[href*='/product/']",
        "link_pattern": "/product/",
        "domain": "https://www.kanadoll.jp",
        "age_selectors": [
            '#agy-accept',
            'button:has-text("はい")',
            'a:has-text("はい")',
            'text="はい"',
            '._ymcart_popup_close_button'
        ]
    },
    "whodoll": {
        "base_url": "https://www.whodoll.com/product-search-%20",
        "page_pattern": "-p{page}",
        "link_selector": "div.cardProduct a",
        "link_pattern": "/",
        "domain": "https://www.whodoll.com",
        "age_selectors": [],
        "custom_handler": "whodoll"
    },
    "sweetmate": {
        "base_url": "https://www.sweetmate.jp/Search-%E3%83%89%E3%83%BC%E3%83%AB/list-r{page}.html",
        "page_pattern": "list-r{page}.html",
        "link_selector": "a[href*='/product-p']",
        "link_pattern": "/product-p",
        "domain": "https://www.sweetmate.jp",
        "age_selectors": [
            '.age_btn:first-child',
            'button:has-text("はい")',
            'a:has-text("はい")',
            'text="はい"',
            '._ymcart_popup_close_button'
        ]
    },
    "dachiwife": {
        "base_url": "https://www.dachiwife.com/new-arrivals-{page}.html",
        "page_pattern": "-{page}.html",
        "link_selector": "div.product-block a",
        "link_pattern": ".html",
        "domain": "https://www.dachiwife.com",
        "age_selectors": [
            '.restriction-btn.restriction-confirm',
            'button:has-text("はい")',
            'a:has-text("はい")',
            'text="はい"'
        ]
    },
    "angeldoll": {
        "base_url": "https://www.angeldoll.jp/product-search-%20",
        "page_pattern": "?page={page}",
        "link_selector": "div.item-box a.pic-box",
        "link_pattern": "/product/",
        "domain": "https://www.angeldoll.jp",
        "age_selectors": [
            '.restriction-btn.restriction-confirm',
            'button:has-text("はい")',
            'a:has-text("はい")',
            'text="はい"'
        ]
    },
    "rosemarydoll": {
        "base_url": "https://www.rosemarydoll.jp/?s=++&post_type=product",
        "page_pattern": "page={page}",
        "link_selector": "a[href*='/product/']",
        "link_pattern": "/product/",
        "domain": "https://www.rosemarydoll.jp",
        "age_selectors": [],
        "custom_handler": "rosemary"
    },
    "nkdollshop": {
        "base_url": "https://www.nkdollshop.com/collections/all?page={page}",
        "page_pattern": "page={page}",
        "link_selector": "a[href*='/products/']",
        "link_pattern": "/products/",
        "domain": "https://www.nkdollshop.com",
        "age_selectors": []
    },
}


# ============================================================
# ★ 材質抽出ロジック
# ============================================================
def extract_material_from_text(text):
    if not text:
        return None
    keywords = [
        r'シリコン', r'TPE', r'PVC', r'STPE', r'Silicon',
        r'ビニール', r'シリコーン', r'シリコン\+TPE', r'シリコン＆TPE',
        r'シリコン/TPE', r'シリコン製', r'フルシリコン', r'TPE製',
        r'ソフビ', r'エラストマー'
    ]
    for pattern in keywords:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result = match.group(0)
            result = re.sub(r'製$|素材$|タイプ$|材質$', '', result)
            return result.strip()
    if len(text) > 30:
        return None
    return text.strip()


# ============================================================
# ★ URLバリデーション関数
# ============================================================
def is_valid_url(url):
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if url.startswith('#') or url.startswith('javascript:'):
        return False
    if re.match(r'^https?://', url, re.IGNORECASE):
        return True
    if url.startswith('/') or url.startswith('./') or url.startswith('../'):
        return True
    return False


# ============================================================
# ヘルパー関数
# ============================================================
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
    if url:
        if '/custom-clothes' in url or '/Search-' in url or '/love-doll-custom-order-balance/' in url:
            logging.info(f"スキップ（URLパターン）: {url}")
            return True
        if 'homecoming' in url or '里帰り' in url:
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


def load_error_urls():
    error_urls = set()
    try:
        with open(ERROR_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        url = parts[1].strip()
                        if url.startswith('http'):
                            error_urls.add(url)
    except:
        pass
    return error_urls


def log_error(url, msg):
    with open(ERROR_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {url} | {msg}\n")


def extract_price(text):
    if not text:
        return None
    if re.search(r'^0\s*(円|$)', text):
        return None
    discount_match = re.search(r'(\d+)\s*[%％]\s*(?:OFF|オフ|割引)', text, re.IGNORECASE)
    discount_rate = None
    if discount_match:
        discount_rate = int(discount_match.group(1)) / 100
    numbers = re.findall(r'([\d,]+)', text)
    if not numbers:
        return None
    int_numbers = [int(n.replace(',', '')) for n in numbers]
    int_numbers = [n for n in int_numbers if n > 0]
    if not int_numbers:
        return None
    if len(int_numbers) >= 2:
        if discount_rate is not None and 0 < discount_rate < 1:
            return str(int(round(int_numbers[0] / (1 - discount_rate))))
        return str(min(int_numbers))
    price = int_numbers[0]
    if discount_rate is not None and 0 < discount_rate < 1:
        return str(int(round(price / (1 - discount_rate))))
    return str(price)


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

    if 'dachiwife.com' in url:
        brand_map = {
            'Art-doll': 'Art-Doll',
            'Art Doll': 'Art-Doll',
            'Strawberry Garden': 'Strawberry Garden',
            'Game Lady': 'Game Lady',
            'Irontech': 'Irontech Doll',
            'WM': 'WM Doll',
            'Aotume': 'Aotume Doll',
            'Sino': 'Sino Doll',
            'SHEDOLL': 'SHEDOLL',
            'FUDOLL': 'FUDOLL',
            'Real Lady': 'Real Lady',
            'ElsaBabe': 'ElsaBabe',
            'Fanreal': 'FANREAL',
            'RZR': 'RZR Doll',
            '蛍火日記': '蛍火日記',
            '羊角社': '羊角社Doll',
        }
        for key, val in brand_map.items():
            if key in product_name:
                metadata['manufacturer'] = val
                break

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


async def scrape_one(page, url, processed_urls, max_retries=3):
    if url in processed_urls:
        return None

    print(f"  処理中: {url}")
    html = None

    if 'dachiwife.com' in url:
        wait_until = 'networkidle'
    else:
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

            if 'dachiwife.com' in url:
                try:
                    await page.wait_for_selector('#product-show-price', timeout=10000)
                except:
                    try:
                        await page.wait_for_selector('.price-box', timeout=5000)
                    except:
                        pass

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

    price = None
    price_elem = soup.find('div', class_='price') or soup.find('p', class_='price')
    if price_elem:
        price = extract_price(price_elem.get_text(strip=True))
    if price is None:
        for text in soup.stripped_strings:
            if '円' in text and len(text) < 50:
                price = extract_price(text)
                if price is not None:
                    break
    if price is None and 'dachiwife.com' in url:
        price_span = soup.select_one('#product-show-price')
        if price_span:
            price_text = price_span.get_text(strip=True)
            price = extract_price(price_text)

    if price is None:
        price = "取得できず"

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

        if '材質' in variant:
            raw_material = variant['材質']
            if raw_material:
                cleaned = extract_material_from_text(raw_material)
                if cleaned:
                    variant['材質'] = cleaned
                else:
                    del variant['材質']
        elif '素材' in variant:
            raw_material = variant['素材']
            if raw_material:
                cleaned = extract_material_from_text(raw_material)
                if cleaned:
                    variant['材質'] = cleaned
                    if '素材' in variant:
                        del variant['素材']
                else:
                    if '素材' in variant:
                        del variant['素材']

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
# ★ 修正版 collect_urls_by_config（domcontentloaded + 強制待機 + headless=False）
# ============================================================
def extract_whodoll_links(soup, domain):
    collected = set()
    links = soup.select('div.cardProduct a')
    if not links:
        all_links = soup.find_all('a', href=True)
        links = [a for a in all_links if '/product-search-' not in a.get('href', '')]
    for a in links:
        href = a.get('href')
        if not href:
            continue
        if href.startswith('/'):
            full_url = domain + href
        elif href.startswith('http'):
            full_url = href
        else:
            continue
        if '/product-search-' in full_url:
            continue
        if full_url == domain + '/':
            continue
        if '/#' in full_url or full_url.endswith('/#'):
            continue
        full_url = re.sub(r'\?.*$', '', full_url)
        collected.add(full_url)
    return collected


async def collect_urls_by_config(site_name, config, max_pages=None):
    collected = set()
    print(f"    🌐 ブラウザを起動中...")
    async with async_playwright() as p:
        # ★★★ 重要修正: headless=False に変更（Cloudflare対策） ★★★
        browser = await p.chromium.launch(
            headless=False,  # ブラウザウィンドウを表示（Cloudflare突破に必須）
            slow_mo=100,     # 動作をやや遅くして安定性向上
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        # ★ page.route による abort を完全に停止（Cloudflare対策）
        # async def route_handler(route):
        #     if route.request.resource_type in ('image', 'media', 'font'):
        #         await route.abort()
        #     else:
        #         await route.continue_()
        # await page.route('**/*', route_handler)

        ymcart_sites = ['dolltime', 'bijindoll', 'ramondoll', 'rakuendoll', 'oldoll', 'sweetmate']
        use_force_wait = site_name in ymcart_sites

        page_num = 1
        while True:
            print(f"    📄 {site_name} ページ {page_num} を収集中...")

            if config.get("custom_handler") == "rosemary":
                url = config["base_url"] if page_num == 1 else config["base_url"] + f"&page={page_num}"
            elif site_name == "whodoll":
                url = config["base_url"] if page_num == 1 else config["base_url"] + f"-p{page_num}"
            elif site_name == "angeldoll":
                url = config["base_url"] if page_num == 1 else config["base_url"] + f"?page={page_num}"
            else:
                url = config["base_url"].format(page=page_num)
                if page_num == 1 and "page=" in url:
                    url = url.replace("page=1", "").replace("?&", "?").replace("&&", "&")
                    if url.endswith("?"):
                        url = url[:-1]

            try:
                await page.goto(url, timeout=60000, wait_until='domcontentloaded')
                print(f"    🔍 ページ読み込み完了（domcontentloaded）")

                if use_force_wait:
                    print(f"    🔍 レンダリング完了を待機中...")
                    try:
                        await page.wait_for_selector('a[href*="/product-p"]', timeout=15000, state='visible')
                        print(f"    ✅ 商品リンクを検出しました（wait_for_selector）")
                    except Exception as e:
                        print(f"    ⚠️ 商品リンク検出タイムアウトまたはエラー: {e}")

                for selector in config.get("age_selectors", []):
                    try:
                        await page.click(selector, timeout=2000)
                    except:
                        pass

                html = await page.content()
                print(f"    🔍 HTML取得後のタイトル: {await page.title()}")
                print(f"    🔍 HTMLサイズ: {len(html)} 文字")

            except Exception as e:
                print(f"    ❌ {site_name} ページ {page_num} 読み込み失敗: {e}")
                break

            soup = BeautifulSoup(html, 'html.parser')

            title_tag = soup.find('title')
            if title_tag:
                print(f"    🔍 ページタイトル（soup）: {title_tag.text.strip()}")
                if 'Checking your browser' in title_tag.text or 'Just a moment' in title_tag.text:
                    print("    ⚠️ Cloudflare/DDOSガードが検出されました。リトライまたは待機時間延長が必要です。")

            if not soup.find('body'):
                print("    ⚠️ bodyタグが見つかりません。空のHTMLの可能性があります。")
                break

            error_urls = load_error_urls()
            if config.get("custom_handler") == "whodoll":
                page_links = extract_whodoll_links(soup, config["domain"])
                for link in page_links:
                    if link not in error_urls:
                        collected.add(link)
            else:
                link_selectors = [config["link_selector"], 'div.product_item a.pic']
                links = []
                for sel in link_selectors:
                    links = soup.select(sel)
                    if links:
                        print(f"    🔍 セレクタ '{sel}' で {len(links)} 件のリンクを検出")
                        break
                if not links:
                    all_links = soup.find_all('a', href=True)
                    links = [a for a in all_links if config["link_pattern"] in a.get('href', '')]
                    print(f"    🔍 フォールバック全aタグから {len(links)} 件のリンクを検出")

                for a in links:
                    href = a.get('href')
                    if not href or not is_valid_url(href):
                        continue
                    if href.startswith('/'):
                        full_url = config["domain"] + href
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        continue
                    full_url = re.sub(r'\?.*$', '', full_url)
                    if full_url.endswith(('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
                        continue
                    if full_url in error_urls:
                        continue
                    collected.add(full_url)

            print(f"    📊 {site_name} ページ {page_num}: 現在 {len(collected)} 件のURLを収集済み")

            # ★ 修正済み：サポートされない疑似クラスを削除
            next_selectors = ['a.next', 'li.next a', '.pagination a[rel="next"]', 'a[title="次へ"]']
            next_link = None
            for sel in next_selectors:
                next_link = soup.select_one(sel)
                if next_link:
                    print(f"    🔍 次へボタンを '{sel}' で検出")
                    break
            
            # ★ テキストベースのフォールバック（BeautifulSoupは:has-textをサポートしないため）
            if not next_link:
                for a in soup.find_all('a', href=True):
                    txt = a.get_text(strip=True)
                    if txt in ['次へ', '›', '>']:
                        next_link = a
                        print(f"    🔍 次へボタンをテキスト '{txt}' で検出（フォールバック）")
                        break

            if not next_link:
                print(f"    ⏹️ {site_name}: 次へボタンがありません。最終ページと判断します。")
                break
            page_num += 1
            if max_pages and page_num > max_pages:
                print(f"    ⏹️ {site_name}: 最大ページ数 {max_pages} に達しました。")
                break
            await asyncio.sleep(1)

        await browser.close()
    print(f"    ✅ {site_name}: 合計 {len(collected)} 件のURLを収集しました（{page_num}ページ分）")
    return collected


# ============================================================
# メイン関数
# ============================================================
async def main():
    start_time = time.time()
    print("=" * 60)
    print(f"🚀 スクレイピングを開始します（対象: {SCRAPE_TARGET}）")
    print(f"🕒 開始時刻: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    available_sites = list(SITE_CONFIGS.keys())

    if SCRAPE_TARGET == 'all':
        target_sites = available_sites
    else:
        target_sites = [SCRAPE_TARGET]

    for site_name in target_sites:
        if site_name not in SITE_CONFIGS:
            print(f"⚠️ 不明なサイト: {site_name}（スキップします）")
            continue

        print(f"\n{'='*60}")
        print(f"🔍 [{site_name}] のURL収集を開始します...")
        print(f"{'='*60}")

        try:
            urls = await collect_urls_by_config(site_name, SITE_CONFIGS[site_name], max_pages=MAX_PAGES_PER_CATEGORY)
            print(f"  ✅ {site_name}: {len(urls)} 件のURLを収集")
        except Exception as e:
            print(f"  ❌ {site_name}: 収集中にエラーが発生しました: {e}")
            continue

        if not urls:
            print(f"  ⏭️ {site_name}: URLが0件のためスキップします")
            continue

        processed = load_processed_urls()
        error_urls = load_error_urls()
        new_urls = [url for url in urls if url not in processed and url not in error_urls]
        print(f"  📊 既処理: {len(processed)} 件, エラー履歴: {len(error_urls)} 件, 新規: {len(new_urls)} 件")

        if not new_urls:
            print(f"  ✅ {site_name}: 新規URLはありません。次のサイトに進みます。")
            continue

        print(f"  🔄 {site_name}: スクレイピングを実行します（{len(new_urls)}件）...")

        success_count = 0
        error_count = 0

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await prepare_page(page)

            try:
                for i, url in enumerate(new_urls, 1):
                    print(f"\n  --- {i}/{len(new_urls)} ---")
                    result = await scrape_one(page, url, processed)
                    if result:
                        success_count += 1
                    else:
                        error_count += 1
                    await asyncio.sleep(1.5)
            finally:
                await browser.close()

        print(f"  ✅ {site_name}: 完了（成功 {success_count} 件, エラー {error_count} 件）")

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"✅ 全サイトのスクレイピングが完了しました！")
    print(f"🕒 経過時間: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())