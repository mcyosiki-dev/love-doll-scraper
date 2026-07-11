# -*- coding: utf-8 -*-
"""
全サイト（オリエント工業・カレンドールを除く）の2ページ分の商品を一括スクレイピングする
（ベースURL修正版：yourdoll/per_page=100, whodoll/product-search-%20, angeldoll/product-search-%20, rosemarydoll/++）
"""
import asyncio
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from run_all_scrapers import scrape_one, load_processed_urls, prepare_page

# ============================================================
# 各サイトの設定（オリエント・カレンドールを除外）
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
    # ★ 修正：per_page=100 に変更
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
    # ★ 修正：product-search-%20 に変更
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
    # ★ 修正：product-search-%20 に変更
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
    # ★ 修正：s=++ に変更（半角スペース2つ）
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
# 年齢確認突破関数
# ============================================================
async def handle_age_verification(page, selectors):
    if not selectors:
        return
    for selector in selectors:
        try:
            await page.click(selector, timeout=3000)
            await page.wait_for_timeout(1000)
            return True
        except:
            continue
    return False

# ============================================================
# Whodoll 専用リンク抽出
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

# ============================================================
# 各サイトから2ページ分の商品URLを収集
# ============================================================
async def collect_sample_urls(site_name, config, max_pages=2):
    collected = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        async def route_handler(route):
            if route.request.resource_type in ('image', 'media', 'font'):
                await route.abort()
            else:
                await route.continue_()
        await page.route('**/*', route_handler)

        for page_num in range(1, max_pages + 1):
            # ★ サイト別のURL生成
            if config.get("custom_handler") == "rosemary":
                if page_num == 1:
                    url = config["base_url"]
                else:
                    url = config["base_url"] + f"&page={page_num}"
            elif site_name == "whodoll":
                if page_num == 1:
                    url = config["base_url"]
                else:
                    # whodoll のページネーションは -p{page}
                    url = config["base_url"] + f"-p{page_num}"
            elif site_name == "angeldoll":
                if page_num == 1:
                    url = config["base_url"]
                else:
                    # angeldoll は ?page={page} を追加（base_url に含まれていないため）
                    url = config["base_url"] + f"?page={page_num}"
            else:
                url = config["base_url"].format(page=page_num)
                # 1ページ目は page=1 を除去（既に base_url に含まれている場合）
                if page_num == 1 and "page=" in url:
                    url = url.replace("page=1", "").replace("?&", "?").replace("&&", "&")
                    if url.endswith("?"):
                        url = url[:-1]

            try:
                await page.goto(url, timeout=45000, wait_until='domcontentloaded')
                await handle_age_verification(page, config.get("age_selectors", []))
                await page.wait_for_timeout(2000)
                html = await page.content()
            except Exception as e:
                print(f"    ⚠️ {site_name} ページ {page_num} 読み込み失敗: {e}")
                continue

            soup = BeautifulSoup(html, 'html.parser')
            if config.get("custom_handler") == "whodoll":
                page_links = extract_whodoll_links(soup, config["domain"])
                for link in page_links:
                    collected.add(link)
                continue

            links = soup.select(config["link_selector"])
            if not links:
                all_links = soup.find_all('a', href=True)
                links = [a for a in all_links if config["link_pattern"] in a.get('href', '')]
            for a in links:
                href = a.get('href')
                if not href:
                    continue
                if href.startswith('/'):
                    full_url = config["domain"] + href
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                full_url = re.sub(r'\?.*$', '', full_url)
                collected.add(full_url)
        await browser.close()
    return collected

# ============================================================
# メイン
# ============================================================
async def main():
    print("=" * 60)
    print("🚀 全サイト（オリエント・カレンドール除く）の2ページ分を一括スクレイピング")
    print("=" * 60)

    # 既処理URLを読み込む
    processed = load_processed_urls()
    print(f"📊 既処理: {len(processed)} 件")

    # 全サイトのURLを収集
    print("\n📡 ステップ1: 各サイトの2ページ分の商品URLを収集...")
    all_urls = set()
    for site_name, config in SITE_CONFIGS.items():
        print(f"\n  [{site_name}]")
        urls = await collect_sample_urls(site_name, config, max_pages=2)
        print(f"    ✅ {len(urls)} 件のURLを収集")
        all_urls.update(urls)

    print(f"\n📊 合計 {len(all_urls)} 件のURLを収集しました")

    # 未処理をフィルタリング
    new_urls = [url for url in all_urls if url not in processed]
    print(f"📊 新規URL: {len(new_urls)} 件")

    if not new_urls:
        print("✅ 新規URLはありません。処理を終了します。")
        return

    # スクレイピング実行
    print("\n🔄 ステップ2: スクレイピングを実行します...")
    success_count = 0
    error_count = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await prepare_page(page)

        for i, url in enumerate(new_urls, 1):
            print(f"\n--- {i}/{len(new_urls)} ---")
            result = await scrape_one(page, url, processed)
            if result:
                success_count += 1
            else:
                error_count += 1
            await asyncio.sleep(1.5)

        await browser.close()

    print("\n" + "=" * 60)
    print(f"✅ 処理完了！")
    print(f"📊 処理結果: 成功 {success_count} 件, エラー {error_count} 件")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())