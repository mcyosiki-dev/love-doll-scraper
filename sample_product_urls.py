# -*- coding: utf-8 -*-
"""
全サイトの商品一覧ページから、2ページ分の商品URLをサンプリングするスクリプト
年齢確認ポップアップ突破機能付き（2026-07-11 対応版）
"""
import asyncio
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# ============================================================
# 各サイトの設定（ベースURL、セレクタ、年齢確認セレクタ）
# ============================================================
SITE_CONFIGS = {
    # ---------- YMCart系（_.ymcart_popup_close_button が有効） ----------
    "dolltime": {
        "base_url": "https://www.dolltime.jp/Search-%E3%83%89%E3%83%BC%E3%83%AB/list-r{page}.html",
        "page_pattern": "list-r{page}.html",
        "link_selector": "a[href*='/product-p']",
        "link_pattern": "/product-p",
        "domain": "https://www.dolltime.jp",
        "age_selectors": []  # 年齢確認なし
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
    "orient_doll": {
        "base_url": "https://www.orient-doll.com/head-list/?isShow=all&page={page}",
        "page_pattern": "page={page}",
        "link_selector": "a[href*='/product/']",
        "link_pattern": "/product/",
        "domain": "https://www.orient-doll.com",
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

    # ---------- YourDoll / Kanadoll（独自の年齢確認） ----------
    "yourdoll": {
        "base_url": "https://yourdoll.jp/shop/?page={page}&per_page=36",
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

    # ---------- Whodoll（独自構造） ----------
    "whodoll": {
        "base_url": "https://www.whodoll.com/product-search-ラブドール",
        "page_pattern": "-p{page}",
        "link_selector": "div.cardProduct a",
        "link_pattern": "/",  # 特殊：トップへのリンクを除外する
        "domain": "https://www.whodoll.com",
        "age_selectors": [],  # 年齢確認なし
        "custom_handler": "whodoll"  # 特殊処理フラグ
    },

    # ---------- SweetMate（.age_btn） ----------
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

    # ---------- Dachiwife（.restriction-btn） ----------
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

    # ---------- AngelDoll（.restriction-btn） ----------
    "angeldoll": {
        "base_url": "https://www.angeldoll.jp/lovely-cute-love-doll?page={page}",
        "page_pattern": "page={page}",
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

    # ---------- RosemaryDoll（なし） ----------
    "rosemarydoll": {
        "base_url": "https://www.rosemarydoll.jp/?page={page}",
        "page_pattern": "page={page}",
        "link_selector": "a[href*='/product/']",
        "link_pattern": "/product/",
        "domain": "https://www.rosemarydoll.jp",
        "age_selectors": []  # 年齢確認なし
    },

    # ---------- Karendoll（WordPress系：要確認） ----------
    "karendoll": {
        "base_url": "https://www.karendoll.com/?page={page}",
        "page_pattern": "page={page}",
        "link_selector": "a[href*='/product/']",
        "link_pattern": "/product/",
        "domain": "https://www.karendoll.com",
        "age_selectors": []  # 年齢確認なし（要確認）
    },

    # ---------- NKDollShop（Shopify系） ----------
    "nkdollshop": {
        "base_url": "https://www.nkdollshop.com/collections/all?page={page}",
        "page_pattern": "page={page}",
        "link_selector": "a[href*='/products/']",
        "link_pattern": "/products/",
        "domain": "https://www.nkdollshop.com",
        "age_selectors": []  # 年齢確認なし（要確認）
    },
}

# ============================================================
# 年齢確認突破関数
# ============================================================
async def handle_age_verification(page, selectors):
    """
    指定されたセレクタリストを順に試行し、年齢確認ポップアップを突破する
    """
    if not selectors:
        return

    for selector in selectors:
        try:
            await page.click(selector, timeout=3000)
            print(f"    ✅ 年齢確認突破: {selector}")
            await page.wait_for_timeout(1000)
            return True
        except:
            continue
    return False

# ============================================================
# Whodoll 専用のリンク抽出（特殊処理）
# ============================================================
def extract_whodoll_links(soup, domain):
    """
    Whodoll の商品リンクは div.cardProduct a だが、
    トップページへのリンク（/）や製品一覧へのリンクを除外する必要がある
    """
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

        # 除外パターン
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
# 各サイトから商品URLを収集（2ページ分）
# ============================================================
async def collect_sample_urls(site_name, config, max_pages=2):
    """
    指定サイトから最大 max_pages ページ分の商品URLを収集
    """
    collected = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # User-Agent偽装
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
        })

        # 画像・フォントブロック（高速化）
        async def route_handler(route):
            if route.request.resource_type in ('image', 'media', 'font'):
                await route.abort()
            else:
                await route.continue_()
        await page.route('**/*', route_handler)

        for page_num in range(1, max_pages + 1):
            # URL生成
            if site_name == "whodoll":
                if page_num == 1:
                    url = config["base_url"]
                else:
                    url = config["base_url"] + f"-p{page_num}"
            else:
                url = config["base_url"].format(page=page_num)
                # 1ページ目はページ番号なしの場合がある（例：yourdoll）
                if page_num == 1 and "page=" in url:
                    url = url.replace("page=1", "").replace("?&", "?").replace("&&", "&")
                    if url.endswith("?"):
                        url = url[:-1]

            print(f"  🔍 {site_name} ページ {page_num}: {url}")

            try:
                await page.goto(url, timeout=45000, wait_until='domcontentloaded')

                # 年齢確認処理
                await handle_age_verification(page, config.get("age_selectors", []))

                await page.wait_for_timeout(2000)
                html = await page.content()

            except Exception as e:
                print(f"    ⚠️ ページ読み込み失敗: {e}")
                continue

            soup = BeautifulSoup(html, 'html.parser')

            # 特殊処理（Whodoll）
            if config.get("custom_handler") == "whodoll":
                page_links = extract_whodoll_links(soup, config["domain"])
                for link in page_links:
                    collected.add(link)
                print(f"    ✅ {len(page_links)} 件の商品URLを収集（累計: {len(collected)} 件）")
                continue

            # 通常処理
            links = soup.select(config["link_selector"])
            if not links:
                # 代替：すべてのaタグからパターンマッチ
                all_links = soup.find_all('a', href=True)
                links = [a for a in all_links if config["link_pattern"] in a.get('href', '')]

            found = 0
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

                # クエリパラメータを除去
                full_url = re.sub(r'\?.*$', '', full_url)
                collected.add(full_url)
                found += 1

            print(f"    ✅ {found} 件の商品URLを収集（累計: {len(collected)} 件）")

        await browser.close()

    return collected

# ============================================================
# メイン
# ============================================================
async def main():
    print("=" * 60)
    print("🔍 全サイトから2ページ分の商品URLをサンプリング（年齢確認突破機能付き）")
    print("=" * 60)

    all_results = {}

    for site_name, config in SITE_CONFIGS.items():
        print(f"\n--- {site_name} ---")
        try:
            urls = await collect_sample_urls(site_name, config, max_pages=2)
            all_results[site_name] = urls
            print(f"  📊 合計: {len(urls)} 件のURLを収集")
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            all_results[site_name] = set()

    # 結果サマリー
    print("\n" + "=" * 60)
    print("📋 収集結果サマリー")
    print("=" * 60)

    for site_name, urls in all_results.items():
        print(f"\n{site_name}: {len(urls)} 件")
        for i, url in enumerate(list(urls)[:5], 1):
            print(f"  {i}. {url}")
        if len(urls) > 5:
            print(f"  ... 他 {len(urls) - 5} 件")

    print("\n" + "=" * 60)
    print("✅ サンプリング完了")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())