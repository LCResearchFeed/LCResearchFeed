set LOG=C:\Users\mkoni\LCResearchFeed\scheduler_log.txt
set PROJECT=C:\Users\mkoni\LCResearchFeed

powershell -Command "Add-Content '%LOG%' ('[' + (Get-Date) + ']')"
powershell -Command "Add-Content '%LOG%' ('Session: ' + $env:SESSIONNAME)"

cd /d "%PROJECT%"
powershell -Command "python lc_scraper.py | Tee-Object -FilePath '%LOG%'"

powershell -Command "Add-Content '%LOG%' '------------------------------'"
