Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "taskkill /F /IM python.exe /FI ""WINDOWTITLE eq *server*""", 0, True
WshShell.Run "taskkill /F /IM python.exe", 0, True
