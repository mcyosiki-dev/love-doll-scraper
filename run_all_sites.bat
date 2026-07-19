@echo off
set MAX_PAGES_PER_CATEGORY=

echo ============================================================
echo サイトを順次実行します（1サイトずつ独立プロセス）
echo ============================================================

for %%s in (dolltime bijindoll ramondoll rakuendoll oldoll yourdoll kanadoll whodoll sweetmate dachiwife angeldoll rosemarydoll nkdollshop) do (
    echo.
    echo ============================================================
    echo [%%s] を実行中...
    echo ============================================================
    set SCRAPE_TARGET=%%s
    python run_all_scrapers.py
    echo.
    echo [%%s] 完了
    echo.
)

echo ============================================================
echo 全サイトの処理が完了しました！
echo ============================================================
pause