powershell -Command "Add-Content scheduler_log.txt ('[' + (Get-Date) + ']')"
powershell -Command "Add-Content scheduler_log.txt ('Session: ' + $env:SESSIONNAME)"

cd /d "C:\Users\mkoni\LCResearchFeed"

powershell -Command "python lc_scraper.py | Tee-Object -FilePath scheduler_log.txt"

powershell -Command "Add-Content scheduler_log.txt '------------------------------'"
