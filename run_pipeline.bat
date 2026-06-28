@echo off

powershell -Command "Add-Content scheduler_log.txt ('[' + (Get-Date) + ']')"
powershell -Command "Add-Content scheduler_log.txt ('Session: ' + $env:SESSIONNAME)"

cd /d "C:\Users\mkoni\LC_Research_project"
"C:\Users\mkoni\AppData\Local\Programs\Python\Python314\python.exe" lc_scraper.py >> scheduler_log.txt 2>&1

powershell -Command "Add-Content scheduler_log.txt '------------------------------'"
