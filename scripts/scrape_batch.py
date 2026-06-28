import asyncio
import json
import re
import time
import sys
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# --- jp-dolls.com の収集対象カテゴリ（6つ） ---
CATEGORY_URLS = [
    "https://www.jp-dolls.com/category/c2.html",   # TPE製
    "https://www.jp-dolls.com/category/c25.html",  # シリコン製
    "https://www.jp-dolls.com/category/c24.html",  # シリコンヘッド
    "https://www.jp-dolls.com/category/c41.html",  # ミニドール
    "https://www.jp-dolls.com/category/c15.html",  # 男性型・ふたなり
    "https://www.jp-dolls.com/category/c38.html",  # 半身・トルソー
]

# --- 表記揺れ正規化 ---
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

# --- 処理済みURLを読み込む ---
def load_processed_urls():
    try:
        with open('all_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {item['商品URL'] for item in data}
    except:
        return set()

# --- エラーログに記録 ---
def log_error(url):
    with open('error.log', 'a', encoding='utf-8') as f:
        f.write(url + '\n')

# --- 価格抽出（割引率対応） ---
def extract_price(text):
    if not text:
        return "取得できず"
    
    # 割引率を検出
    discount_match = re.search(r'(\d+)\s*[%％]\s*(?:OFF|オフ|割引)', text, re.IGNORECASE)
    discount_rate = None
    if discount_match:
        discount_rate = int(discount_match.group(1)) / 100
    
    # すべての数値を抽出
    numbers = re.findall(r'([\d,]+)', text)
    if not numbers:
        return "取得できず"
    
    int_numbers = [int(n.replace(',', '')) for n in numbers]
    
    # 割引率がある場合 → 最後の数値（セール価格）から元値を計算
    if discount_rate is not None and len(int_numbers) >= 1:
        final_price = int_numbers[-1]
        if discount_rate > 0 and discount_rate < 1:
            original_price = final_price / (1 - discount_rate)
            return str(int(round(original_price)))
        else:
            return str(final_price)
    
    # 割引率がない場合 → 最初の数値を元値として返す
    return str(int_numbers[0])

# --- 商品ページのスクレイピング ---
async def scrape_one(url, output_file="all_data.json"):
    processed_urls = load_processed_urls()
    if url in processed_urls:
        print(f"⏭️ スキップ（既に処理済み）: {url}")
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print(f"処理中: {url}")
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
            print(f"⚠️ エラー: {e}")
            log_error(url)
            await browser.close()
            return None
        await browser.close()
        soup = BeautifulSoup(html, 'html.parser')
        html_text = soup.get_text()
        
        name_tag = soup.find('h1', class_='product-title') or soup.find('h1')
        product_name = name_tag.text.strip() if name_tag else "不明"
        
        if is_unwanted(product_name, html_text):
            print(f"⏭️ スキップ（不要データ）: {product_name}")
            return None
        
        # --- 価格抽出 ---
        price = "取得できず"
        price_elem = soup.find('div', class_='price') or soup.find('p', class_='price')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price = extract_price(price_text)
            if price != "取得できず":
                print(f"価格: {price}円（要素から抽出）")
        
        if price == "取得できず":
            for text in soup.stripped_strings:
                if '円' in text and len(text) < 50:
                    price = extract_price(text)
                    if price != "取得できず":
                        print(f"価格: {price}円（テキストから抽出）")
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
        
        print(f"✅ 保存完了: {product_name[:30]}...")
        return output

# --- jp-dolls.com 用：複数カテゴリを巡回して商品URLを収集 ---
async def collect_urls_from_jpdolls(max_pages=3):
    collected_urls = set()
    
    try:
        with open('urls.txt', 'r', encoding='utf-8') as f:
            existing_urls = set(line.strip() for line in f if line.strip())
    except:
        existing_urls = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        for category_url in CATEGORY_URLS:
            print(f"\n📂 カテゴリを処理中: {category_url}")
            for page_num in range(1, max_pages + 1):
                if page_num == 1:
                    url = category_url
                else:
                    url = category_url + f"?page={page_num}"
                
                print(f"  🔍 ページをクロール中: {url}")
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
                    await page.wait_for_timeout(5000)
                    html = await page.content()
                except Exception as e:
                    print(f"    ⚠️ ページ読み込み失敗: {e}")
                    break
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # ★ 商品リンクを抽出（/goods/ パターン）
                links = soup.find_all('a', href=True)
                found = False
                for link in links:
                    href = link['href']
                    # ★ 商品詳細ページのURLパターン: /goods/pXXXX.html
                    if '/goods/p' in href and href.endswith('.html'):
                        if href.startswith('/'):
                            full_url = "https://www.jp-dolls.com" + href
                        elif href.startswith('https://'):
                            full_url = href
                        else:
                            continue
                        full_url = re.sub(r'\?.*$', '', full_url)
                        if full_url not in existing_urls and full_url not in collected_urls:
                            collected_urls.add(full_url)
                            found = True
                            print(f"      ✅ 収集: {full_url}")
                
                if not found:
                    print(f"    ⏹️ 商品が見つからなかったため、{page_num}ページ目で終了します。")
                    # デバッグ情報を表示
                    print("    🔍 デバッグ: ページ内のリンク一覧（最初の20件）:")
                    for i, link in enumerate(soup.find_all('a', href=True)[:20]):
                        print(f"      {link.get('href')} ({link.get_text(strip=True)[:30]})")
                    break
                
                # 次へボタンがあれば続行
                next_link = soup.find('a', string=re.compile(r'次へ|Next|›|»'))
                if not next_link and page_num > 1:
                    print(f"    ⏹️ 次へボタンがないため、{page_num}ページ目で終了します。")
                    break
        
        await browser.close()
    
    if collected_urls:
        with open('urls.txt', 'a', encoding='utf-8') as f:
            for url in sorted(collected_urls):
                f.write(url + '\n')
        print(f"\n✅ {len(collected_urls)} 件の新規URLを urls.txt に追加しました。")
    else:
        print("ℹ️ 新規URLは見つかりませんでした。")
    
    return collected_urls

# --- エラーログから再処理する関数 ---
async def retry_errors():
    try:
        with open('error.log', 'r', encoding='utf-8') as f:
            error_urls = [line.strip() for line in f if line.strip()]
    except:
        print("❌ error.log が見つかりません。")
        return
    
    if not error_urls:
        print("ℹ️ エラーログは空です。")
        return
    
    print(f"📋 エラーログに {len(error_urls)} 件のURLがあります。再処理を開始します...")
    for i, url in enumerate(error_urls, 1):
        print(f"\n--- {i}/{len(error_urls)} ---")
        await scrape_one(url)
        time.sleep(1.5)

# --- メイン ---
async def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == '--retry':
            await retry_errors()
            return
        try:
            max_pages = int(sys.argv[1])
        except ValueError:
            print("⚠️ ページ数は数字で指定してください。デフォルトの3を使います。")
            max_pages = 3
    else:
        max_pages = 3
    
    print(f"📡 jp-dolls.com の {len(CATEGORY_URLS)} カテゴリを巡回し、各 {max_pages} ページ分の商品URLを収集します...")
    await collect_urls_from_jpdolls(max_pages=max_pages)
    
    try:
        with open('urls.txt', 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
    except:
        print("❌ urls.txt が見つかりません。")
        return
    
    if not urls:
        print("❌ 収集したURLがありません。")
        return
    
    print(f"📋 合計 {len(urls)} 件のURLを処理します。")
    for i, url in enumerate(urls, 1):
        print(f"\n--- {i}/{len(urls)} ---")
        await scrape_one(url)
        time.sleep(1.5)

if __name__ == "__main__":
    asyncio.run(main())