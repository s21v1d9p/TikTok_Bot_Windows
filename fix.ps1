# fix.ps1 - run via RDP /shell, copies fixed bot files to their installed location
$log = "\\tsclient\botfiles\fix_result.txt"
try {
    # Find tiktok_bot.py anywhere on C: or D:
    $found = Get-ChildItem -Path C:\,D:\ -Filter "tiktok_bot.py" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) {
        $dir = $found.DirectoryName
        Copy-Item "\\tsclient\botfiles\stealth.py" "$dir\stealth.py" -Force
        Copy-Item "\\tsclient\botfiles\tiktok_bot.py" "$dir\tiktok_bot.py" -Force
        "OK: $dir" | Out-File $log -Encoding utf8
    } else {
        "NOT_FOUND" | Out-File $log -Encoding utf8
    }
} catch {
    $_.Exception.Message | Out-File $log -Encoding utf8
}
