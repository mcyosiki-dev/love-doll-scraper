import asyncio
import json
import re
import time
import sys
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# ============================================================
# 1. 設定
# ============================================================
YOURDOLL_CATEGORY = "https://yourdoll.jp/product-category/all-sex-dolls/"
JPDOLL_CATEGORIES = [
    "https://www.jp-dolls.com/category/c2.html",   # TPE製
    "https://www.jp-dolls.com/category/c25.html",  # シリコン製
    "https://www.jp-dolls.com/category/c24.html",  # シリコンヘッド
    "https://www.jp-dolls.com/category/c41.html",  # ミニドール
    "https://www.jp-dolls.com/category/c15.html",  # 男性型・ふたなり
    "https://www.jp-dolls.com/category/c38.html",  # 半身・トルソー
]
MAX_PAGES_PER_CATEGORY = 300  # ★ 全件収集用（テスト時は3に変更）

# ============================================================
# 2. 共通関数（表記揺れ正規化など）
# ============================================================
def normalize_spec_key(key):
    key = key.strip()
    mapping = {
        "トップ": "バスト",
        "バスト": "バスト",
        "アンダー": "アンダーバスト",
        "アンダーバスト": "アンダーバスト",
        "膣深さ": "膣の深さ",
        "肛門深さ": "アナルの深さ",
        "口深さ": "口の深さ",
        "足サイズ": "足のサイズ",
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
    else: return "G以上"

def is_unwanted(product_name, html_text):
    text = product_name + " " + html_text
    if "オナホール" in text or "トルソー" in text:
        return False
    if "里帰り" in product_name or "受付" in product_name:
        return True
    if "404" in product_name or "Page Not Found" in product_name:
        return True
    for kw in ["福袋", "ランダムセット", "ヘッド単体", "ヘッド単品", "ボディ単体"]:
        if kw in text:
            return True
    return False

def determine_type(product_name, spec, html_text):
    text = product_name + " " + html_text
    if "オナホール" in text:
        return "オナホール"
    if "トルソー" in text:
        return "トルソー"
    if any(kw in text for kw in ["男性", "メンズ", "Male"]) and "バスト" not in spec:
        return "男性型"
    if "バスト" in spec or "身長" in spec:
        return "女性型"
    return "不明"

def extract_site_name(url):
    if not url:
        return ''
    domain = re.sub(r'^https?://(www\.)?', '', url)
    return domain.split('/')[0]

def load_processed_urls():
    try:
        with open('all_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {item['商品URL'] for item in data}
    except:
        return set()

def log_error(url, msg):
    with open('error.log', 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {url} | {msg}\n")

# ============================================================
# 3. 商品ページのスクレイピング
# ============================================================
async def scrape_one(url, output_file="all_data.json"):
    processed_urls = load_processed_urls()
    if url in processed_urls:
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print(f"  処理中: {url}")
        try:
            await page.goto(url, timeout=60000)
            try:
                await page.click('button:has-text("はい")', timeout=3000)
            except:
                try:
                    await page.click('a:has-text("はい")', timeout=3000)
                except:
                    try:
                        await page.click('text="はい"', timeout=3000)
                    except:
                        pass
            await page.wait_for_timeout(1000)
            html = await page.content()
        except Exception as e:
            log_error(url, str(e))
            await browser.close()
            return None
        await browser.close()
        soup = BeautifulSoup(html, 'html.parser')
        html_text = soup.get_text()
        
        name_tag = soup.find('h1', class_='product-title') or soup.find('h1')
        product_name = name_tag.text.strip() if name_tag else "不明"
        
        if is_unwanted(product_name, html_text):
            print(f"  ⏭️ スキップ（不要データ）: {product_name}")
            return None
        
        # 価格
        price = "取得できず"
        price_elem = soup.find('div', class_='price') or soup.find('p', class_='price')
        if price_elem:
            m = re.search(r'([\d,]+)', price_elem.get_text(strip=True))
            if m:
                price = m.group(1).replace(',', '')
        if price == "取得できず":
            for text in soup.stripped_strings:
                m = re.search(r'([\d,]+)\s*円', text)
                if m and ('税込' in text or '送料' in text or len(text) < 30):
                    price = m.group(1).replace(',', '')
                    break
        
        spec = {}
        penis = []
        
        for table in soup.find_all('table'):
            if "最小/最大直径" in str(table) or "シリアルナンバー" in str(table):
                rows = table.find_all('tr')
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
                if penis:
                    spec["ペニス"] = penis
                continue
            if '身長' not in str(table):
                continue
            for row in table.find_all('tr'):
                cols = row.find_all(['td', 'th'])
                if len(cols) < 4:
                    continue
                k1, v1 = cols[0].get_text(strip=True), cols[1].get_text(strip=True)
                k2, v2 = cols[2].get_text(strip=True), cols[3].get_text(strip=True)
                if k1 and v1:
                    nk = normalize_spec_key(k1)
                    v = clean_height(v1) if nk == "身長" else clean_spec_value(v1)
                    spec[nk] = v
                if k2 and v2:
                    nk = normalize_spec_key(k2)
                    v = clean_height(v2) if nk == "身長" else clean_spec_value(v2)
                    spec[nk] = v
        
        if not spec:
            spec_section = soup.find(string=re.compile(r'商品仕様'))
            if spec_section:
                parent = spec_section.find_parent()
                if parent:
                    for line in parent.get_text(separator="\n").splitlines():
                        if '：' in line or ':' in line:
                            parts = re.split(r'[：:]', line, maxsplit=1)
                            if len(parts) == 2:
                                k, v = parts[0].strip(), parts[1].strip()
                                if k and v and k not in spec:
                                    nk = normalize_spec_key(k)
                                    v = clean_height(v) if nk == "身長" else clean_spec_value(v)
                                    spec[nk] = v
        
        if not spec:
            for kw in ["素材", "重さ", "高さ", "幅", "長さ", "タイプ", "膣の深さ", "肛門の深さ", "梱包サイズ"]:
                m = re.search(rf'{kw}[：:]\s*([^\n]+)', html_text)
                if m:
                    nk = normalize_spec_key(kw)
                    v = clean_height(m.group(1)) if nk == "身長" else clean_spec_value(m.group(1))
                    spec[nk] = v
        
        if 'バスト' in spec and 'アンダーバスト' in spec:
            cup = calculate_cup(spec['バスト'], spec['アンダーバスト'])
            if cup:
                spec['カップ数'] = cup
        
        spec["大分類"] = determine_type(product_name, spec, html_text)
        spec["サイト名"] = extract_site_name(url)
        
        output = {
            "商品名": product_name,
            "価格": price,
            "商品URL": url,
            "スペックバリエーション": [spec]
        }
        
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
        data.append(output)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"  ✅ 保存完了: {product_name[:30]}...")
        return output

# ============================================================
# 4. URL収集（yourdoll + jpdolls）  ★ ページネーション修正 ★
# ============================================================
async def collect_urls_yourdoll(max_pages=3):
    collected = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for page_num in range(1, max_pages + 1):
            url = YOURDOLL_CATEGORY if page_num == 1 else f"{YOURDOLL_CATEGORY}page/{page_num}/"
            print(f"  🔍 yourdoll ページをクロール中: {url}")
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(2000)
                html = await page.content()
            except Exception as e:
                print(f"    ⚠️ ページ読み込み失敗（最終ページの可能性）: {e}")
                break
            soup = BeautifulSoup(html, 'html.parser')
            links = soup.find_all('a', href=True)
            found = False
            for link in links:
                href = link['href']
                if '/product/' in href and '/product-category/' not in href:
                    full = "https://yourdoll.jp" + href if href.startswith('/') else href
                    full = re.sub(r'\?.*$', '', full)
                    collected.add(full)
                    found = True
            if not found:
                print(f"    ⏹️ 商品リンクが見つからなかったため終了")
                break
        await browser.close()
    return collected

async def collect_urls_jpdolls(max_pages=3):
    collected = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for cat_url in JPDOLL_CATEGORIES:
            for page_num in range(1, max_pages + 1):
                url = cat_url if page_num == 1 else f"{cat_url}?page={page_num}"
                print(f"  🔍 jpdolls ページをクロール中: {url}")
                try:
                    await page.goto(url, timeout=60000)
                    await page.wait_for_timeout(2000)
                    html = await page.content()
                except Exception as e:
                    print(f"    ⚠️ ページ読み込み失敗（最終ページの可能性）: {e}")
                    break
                soup = BeautifulSoup(html, 'html.parser')
                links = soup.find_all('a', href=True)
                found = False
                for link in links:
                    href = link['href']
                    if '/goods/p' in href and href.endswith('.html'):
                        full = "https://www.jp-dolls.com" + href if href.startswith('/') else href
                        full = re.sub(r'\?.*$', '', full)
                        collected.add(full)
                        found = True
                if not found:
                    print(f"    ⏹️ 商品リンクが見つからなかったため終了")
                    break
        await browser.close()
    return collected

# ============================================================
# 5. メイン（一括実行）
# ============================================================
async def main():
    start_time = time.time()
    print("=" * 60)
    print("🚀 一括スクレイピングを開始します（yourdoll + jpdolls）")
    print(f"🕒 開始時刻: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ---- ステップ1: URL収集 ----
    print("\n📡 ステップ1: 商品URLを収集します...")
    all_urls = set()
    
    print("\n  [yourdoll]")
    yd_urls = await collect_urls_yourdoll(max_pages=MAX_PAGES_PER_CATEGORY)
    print(f"  ✅ yourdoll: {len(yd_urls)} 件のURLを収集")
    all_urls.update(yd_urls)
    
    print("\n  [jp-dolls]")
    jp_urls = await collect_urls_jpdolls(max_pages=MAX_PAGES_PER_CATEGORY)
    print(f"  ✅ jp-dolls: {len(jp_urls)} 件のURLを収集")
    all_urls.update(jp_urls)
    
    print(f"\n📊 合計 {len(all_urls)} 件のURLを収集しました。")

    # ---- ステップ2: 未処理URLをフィルタ ----
    print("\n📋 ステップ2: 未処理のURLをフィルタリングします...")
    processed = load_processed_urls()
    new_urls = [url for url in all_urls if url not in processed]
    print(f"📊 既処理: {len(processed)} 件, 新規: {len(new_urls)} 件")

    if not new_urls:
        print("✅ 新規URLはありません。処理を終了します。")
        return

    # ---- ステップ3: スクレイピング実行 ----
    print("\n🔄 ステップ3: スクレイピングを実行します...")
    success_count = 0
    error_count = 0
    for i, url in enumerate(new_urls, 1):
        print(f"\n--- {i}/{len(new_urls)} ---")
        result = await scrape_one(url)
        if result:
            success_count += 1
        else:
            error_count += 1
        time.sleep(1.5)

    # ---- ステップ4: データベース更新 ----
    print("\n💾 ステップ4: データベースを更新します...")
    import subprocess
    try:
        subprocess.run([sys.executable, "json_to_db.py"], check=True, capture_output=False)
        print("✅ データベース更新完了")
    except Exception as e:
        print(f"⚠️ データベース更新中にエラー: {e}")

    # ---- 完了 ----
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"✅ 一括スクレイピングが完了しました！")
    print(f"📊 処理結果: 成功 {success_count} 件, エラー {error_count} 件")
    print(f"🕒 経過時間: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分)")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())