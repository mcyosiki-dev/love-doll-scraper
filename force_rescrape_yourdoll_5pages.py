import asyncio
import json
import re
import time
import sys
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# ============================================================
# 1. 設定（★ yourdoll 最初の5ページを強制再処理用に変更）
# ============================================================
YOURDOLL_CATEGORY = "https://yourdoll.jp/product-category/all-sex-dolls/"
JPDOLL_CATEGORIES = []  # ★ jp-dolls はスキップ（空リスト）

# ★ yourdoll の最初の5ページだけを処理
MAX_PAGES_PER_CATEGORY = 5

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
        "素材": "材質",
        "Silicon": "シリコン",
        "silicon": "シリコン",
        "シリコーン": "シリコン",
        "シリコン＋TPE": "シリコン/TPE",
        "シリコン＆TPE": "シリコン/TPE",
        "シリコン+TPE": "シリコン/TPE",
        "シリコン&TPE": "シリコン/TPE",
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

# ★★★ ここが重要：常に空のセットを返す（スキップを無効化）★★★
def load_processed_urls():
    return set()

def log_error(url, msg):
    with open('error.log', 'a', encoding='utf-8') as f:
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
        if discount_rate > 0 and discount_rate < 1:
            original_price = final_price / (1 - discount_rate)
            return str(int(round(original_price)))
        else:
            return str(final_price)
    return str(int_numbers[0])

# ============================================================
# 3. 商品ページのスクレイピング（バリエーション対応版）
# ============================================================
async def scrape_one(url, output_file="all_data.json"):
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
        
        price = "取得できず"
        price_elem = soup.find('div', class_='price') or soup.find('p', class_='price')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price = extract_price(price_text)
        
        if price == "取得できず":
            for text in soup.stripped_strings:
                if '円' in text and len(text) < 50:
                    price = extract_price(text)
                    if price != "取得できず":
                        break
        
        spec = {}
        all_specs = []
        penis = []
        
        for table in soup.find_all('table'):
            if "最小/最大直径" in str(table) or "シリアルナンバー" in str(table):
                rows = table.find_all('tr')
                if not rows:
                    continue
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
            current_spec = {}
            for row in table.find_all('tr'):
                cols = row.find_all(['td', 'th'])
                if len(cols) < 4:
                    continue
                k1, v1 = cols[0].get_text(strip=True), cols[1].get_text(strip=True)
                k2, v2 = cols[2].get_text(strip=True), cols[3].get_text(strip=True)
                if k1 and v1:
                    nk = normalize_spec_key(k1)
                    v = clean_height(v1) if nk == "身長" else clean_spec_value(v1)
                    current_spec[nk] = v
                if k2 and v2:
                    nk = normalize_spec_key(k2)
                    v = clean_height(v2) if nk == "身長" else clean_spec_value(v2)
                    current_spec[nk] = v
            if current_spec:
                all_specs.append(current_spec)
        
        if not all_specs:
            spec_section = soup.find(string=re.compile(r'商品仕様'))
            if spec_section:
                parent = spec_section.find_parent()
                if parent:
                    current_spec = {}
                    for line in parent.get_text(separator="\n").splitlines():
                        if '：' in line or ':' in line:
                            parts = re.split(r'[：:]', line, maxsplit=1)
                            if len(parts) == 2:
                                k, v = parts[0].strip(), parts[1].strip()
                                if k and v and k not in current_spec:
                                    nk = normalize_spec_key(k)
                                    v = clean_height(v) if nk == "身長" else clean_spec_value(v)
                                    current_spec[nk] = v
                    if current_spec:
                        all_specs.append(current_spec)
        
        if not all_specs:
            current_spec = {}
            for kw in ["素材", "重さ", "高さ", "幅", "長さ", "タイプ", "膣の深さ", "肛門の深さ", "梱包サイズ"]:
                m = re.search(rf'{kw}[：:]\s*([^\n]+)', html_text)
                if m:
                    nk = normalize_spec_key(kw)
                    v = clean_height(m.group(1)) if nk == "身長" else clean_spec_value(m.group(1))
                    current_spec[nk] = v
            if current_spec:
                all_specs.append(current_spec)
        
        for variant in all_specs:
            if 'バスト' in variant and 'アンダーバスト' in variant:
                cup = calculate_cup(variant['バスト'], variant['アンダーバスト'])
                if cup:
                    variant['カップ数'] = cup
            variant["大分類"] = determine_type(product_name, variant, html_text)
            variant["サイト名"] = extract_site_name(url)
        
        if all_specs:
            for variant in all_specs:
                height = variant.get('身長', '')
                cup = variant.get('カップ数', '')
                variant_name = product_name
                if height or cup:
                    variant_name += f" ({height} {cup})".strip()
                
                output = {
                    "商品名": variant_name,
                    "価格": price,
                    "商品URL": url,
                    "スペックバリエーション": [variant]
                }
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except:
                    data = []
                data.append(output)
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"  ✅ 保存完了（バリエーション）: {variant_name[:30]}...")
            return {"商品名": product_name, "バリエーション数": len(all_specs)}
        else:
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
            print(f"  ✅ 保存完了（フォールバック）: {product_name[:30]}...")
            return output

# ============================================================
# 4. URL収集（★ yourdoll のみ、最大5ページを強制ループ）
# ============================================================
async def collect_urls_yourdoll(max_pages=None):
    collected = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # ★ ページ番号を直接指定してループ（最大5ページ）
        page_limit = max_pages if max_pages else 5
        for page_num in range(1, page_limit + 1):
            url = YOURDOLL_CATEGORY if page_num == 1 else f"{YOURDOLL_CATEGORY}page/{page_num}/"
            print(f"  🔍 yourdoll ページ {page_num} をクロール中: {url}")
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(2000)
                html = await page.content()
            except Exception as e:
                print(f"    ⚠️ ページ読み込み失敗: {e}")
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
            print(f"    ✅ 現在 {len(collected)} 件のURLを収集")
        await browser.close()
    return collected

async def collect_urls_jpdolls(max_pages=None):
    # ★ 空リストのため、何も収集しない
    return set()

# ============================================================
# 5. メイン（一括実行）
# ============================================================
async def main():
    start_time = time.time()
    print("=" * 60)
    print("🚀 yourdoll.jp 最初の5ページを強制再スクレイピングします")
    print(f"🕒 開始時刻: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n📡 ステップ1: 商品URLを収集します...")
    all_urls = set()
    
    print("\n  [yourdoll]")
    yd_urls = await collect_urls_yourdoll(max_pages=MAX_PAGES_PER_CATEGORY)
    print(f"  ✅ yourdoll: {len(yd_urls)} 件のURLを収集")
    all_urls.update(yd_urls)
    
    print("\n  [jp-dolls]")
    jp_urls = await collect_urls_jpdolls()
    print(f"  ✅ jp-dolls: {len(jp_urls)} 件のURLを収集（スキップ）")
    all_urls.update(jp_urls)
    
    print(f"\n📊 合計 {len(all_urls)} 件のURLを収集しました。")

    print("\n📋 ステップ2: スキップ無効化により、すべてのURLを処理します...")
    new_urls = list(all_urls)
    print(f"📊 処理対象: {len(new_urls)} 件")

    if not new_urls:
        print("✅ 処理対象URLはありません。終了します。")
        return

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

    print("\n💾 ステップ4: データベースを更新します...")
    import subprocess
    try:
        subprocess.run([sys.executable, "json_to_db.py"], check=True, capture_output=False)
        print("✅ データベース更新完了")
    except Exception as e:
        print(f"⚠️ データベース更新中にエラー: {e}")

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"✅ yourdoll.jp 最初の5ページの強制再スクレイピングが完了しました！")
    print(f"📊 処理結果: 成功 {success_count} 件, エラー {error_count} 件")
    print(f"🕒 経過時間: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分)")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())