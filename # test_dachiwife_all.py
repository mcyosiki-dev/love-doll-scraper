# test_dachiwife_all.py
import asyncio
from run_all_scrapers import collect_urls_dachiwife, scrape_one, DACHIWIFE_CATEGORIES

async def test_dachiwife_all(limit=20):
    """
    Dachiwife の全カテゴリ・2ページ分のURLを収集し、先頭から limit 件をスクレイピングする。
    limit=None の場合は全件スクレイピングする。
    """
    print("=" * 60)
    print(f"🧪 Dachiwife 全件テスト（最大 {limit if limit else '全'} 件）を開始します")
    print("=" * 60)

    # 1. URL収集（最大2ページ）
    print("\n[ステップ1] URL収集（最大2ページ）...")
    urls = await collect_urls_dachiwife(DACHIWIFE_CATEGORIES, max_pages=2)
    print(f"📊 収集されたURL数: {len(urls)} 件")

    if not urls:
        print("❌ URLが収集できませんでした。終了します。")
        return

    # 2. スクレイピング（先頭から limit 件）
    target_urls = urls[:limit] if limit else urls
    print(f"\n[ステップ2] {len(target_urls)} 件をスクレイピングします...")

    success_count = 0
    error_count = 0
    for i, url in enumerate(target_urls, 1):
        print(f"\n--- {i}/{len(target_urls)}: {url} ---")
        try:
            result = await scrape_one(url)
            if result:
                print(f"✅ 成功: {result.get('商品名')}")
                success_count += 1
            else:
                print("❌ 失敗（スキップまたはエラー）")
                error_count += 1
        except Exception as e:
            print(f"❌ スクレイピング中にエラー: {e}")
            error_count += 1

    print("\n" + "=" * 60)
    print(f"✅ Dachiwife 全件テストが完了しました。")
    print(f"📊 成功: {success_count} 件, エラー: {error_count} 件")
    print("=" * 60)

if __name__ == "__main__":
    # ★ ここで limit の値を変更できます
    # limit=20  → 最初の20件のみテスト（推奨）
    # limit=None → 全件（319件）をテスト（時間がかかります）
    asyncio.run(test_dachiwife_all(limit=20))