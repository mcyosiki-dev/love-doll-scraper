# -*- coding: utf-8 -*-
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from run_all_scrapers import scrape_one, load_processed_urls, prepare_page

async def main():
    # 既存のall_data.jsonから既処理URLを読み込む
    processed = load_processed_urls()

    # orient_urls.txt からURLを読み込む
    url_file = Path(__file__).resolve().parent / 'orient_urls.txt'
    if not url_file.exists():
        print(f"❌ {url_file} が見つかりません")
        return

    with open(url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"📊 合計 {len(urls)} 件のURLを読み込みました")

    # 未処理のURLをフィルタリング
    new_urls = [url for url in urls if url not in processed]
    print(f"📊 既処理: {len(processed)} 件, 新規: {len(new_urls)} 件")

    if not new_urls:
        print("✅ 新規URLはありません。処理を終了します。")
        return

    print("\n🔄 スクレイピングを実行します...")
    success_count = 0
    error_count = 0

    # Playwrightを起動し、pageを再利用
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await prepare_page(page)

        for i, url in enumerate(new_urls, 1):
            print(f"\n--- {i}/{len(new_urls)} ---")
            # scrape_one に page, url, processed を渡す
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