@echo off
setlocal
chcp 65001 >nul
set "MVR_BROWSER_SCRIPT=%~f0"
powershell.exe -NoLogo -NoProfile -Command "$ErrorActionPreference='Stop'; $s=Get-Content -LiteralPath $env:MVR_BROWSER_SCRIPT -Raw -Encoding UTF8; $m='# MVR_BROWSER_PS'; & ([scriptblock]::Create($s.Substring($s.LastIndexOf($m))))"
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
# MVR_BROWSER_PS
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
    $app = Split-Path -Parent $env:MVR_BROWSER_SCRIPT
    $exe = Join-Path $app 'MarVoiReflex.exe'
    $data = Join-Path $app 'Data-MarVoiVoice'
    $statePath = Join-Path $data 'connection.json'
    $expected = '6d6c2d79890254f402e12792fda957f5f43924201b18e8ce48a3def8ee0d1faf'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw '請將本 CMD 放到 MarVoiReflex.exe 旁邊，再雙擊。' }
    if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ine $expected) { throw '執行檔不是已知的 2026-10-31 發行版或檔案受損，請核對版本。' }
    if (Get-Process -Name MarVoiReflex -ErrorAction SilentlyContinue) { throw '請先關閉 MarVoiReflex 白色視窗（Alt+F4）。若仍在執行，請用工作管理員確認後再試。' }
    foreach ($file in @('web\voice\index.html','web\voice\live.js','assets\models\MiniCPM5-2B-Q4_K_M.gguf')) {
        $p = Join-Path $app $file
        if (-not (Test-Path -LiteralPath $p -PathType Leaf) -or (Get-Item -LiteralPath $p).Length -eq 0) { throw ('必要檔案缺失或為空：' + $file) }
    }
    Write-Host '啟動 MarVoiReflex 瀏覽器相容模式。請勿關閉本視窗直到瀏覽器開啟。'
    $started = [DateTime]::UtcNow
    $process = Start-Process -FilePath $exe -ArgumentList '--no-browser' -WorkingDirectory $app -PassThru
    $url = $null
    for ($i=0; $i -lt 120; $i++) {
        if ($process.HasExited) { throw '本機服務已停止。請查看 Data-MarVoiVoice\logs\startup-error.txt。' }
        if ((Test-Path -LiteralPath $statePath) -and (Get-Item -LiteralPath $statePath).LastWriteTimeUtc -ge $started.AddSeconds(-1)) {
            try {
                $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
                $candidate = [Uri]$state.url
                if ($candidate.Scheme -ne 'http' -or $candidate.Host -ne '127.0.0.1' -or $candidate.Port -le 0 -or $candidate.AbsolutePath -ne '/' -or $candidate.UserInfo -or $candidate.Query -ne ('?launch=' + $state.token) -or $state.token -cnotmatch '^[0-9a-f]{48}$') { throw '本機連線資訊格式不正確。' }
                if ($state.origin -ne $candidate.GetLeftPart([UriPartial]::Authority)) { throw '本機來源不一致。' }
                $request = [Net.HttpWebRequest]::Create($candidate)
                $request.Proxy = $null
                $request.AllowAutoRedirect = $false
                $request.Timeout = 2000
                $response = $request.GetResponse()
                try {
                    if ([int]$response.StatusCode -eq 200 -and $response.ContentType -like 'text/html*') { $url = $candidate.AbsoluteUri }
                } finally { $response.Dispose() }
            } catch {}
        }
        if ($url) { break }
        Start-Sleep -Seconds 1
    }
    if (-not $url) { throw '本機 UI 未在預期時間內回應。請查看 Data-MarVoiVoice\logs\startup-error.txt；不要分享 connection.json。' }
    Start-Process $url
    Write-Host '本機 HTML 服務已回應，已要求預設瀏覽器開啟介面。' -ForegroundColor Green
    Write-Host 'AI 模型可能仍在載入；本工具不代表所有功能已通過測試。'
    Write-Host '瀏覽器關閉後，App 會依既有流程停止；若未停止，可從工作管理員確認。'
    exit 0
} catch {
    Write-Host ('啟動未完成：' + $_.Exception.Message) -ForegroundColor Red
    Write-Host '若裝置管理政策禁止執行本機服務或 CMD，請由管理員確認，不要關閉安全性功能。'
    exit 1
}
