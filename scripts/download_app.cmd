@echo off
setlocal
chcp 65001 >nul
set "MVR_INSTALLER=%~f0"
powershell.exe -NoLogo -NoProfile -Command "$ErrorActionPreference='Stop'; $s=Get-Content -LiteralPath $env:MVR_INSTALLER -Raw -Encoding UTF8; $m='# MVR_E2B_PS'; & ([scriptblock]::Create($s.Substring($s.LastIndexOf($m))))"
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
# MVR_E2B_PS
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.IO.Compression.FileSystem
$root = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MarVoiReflex\20261128-E2B'
$cache = Join-Path $root 'downloads'
$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,6)
$stage = Join-Path $root ('stage-' + $stamp)
$final = Join-Path $root ('MarVoiReflex-' + $stamp)
$zipName = 'MarVoiReflex-Gemma4-E2B-Windows-x64.zip'
$zipSha = '43e06d091651cecfb164b246a86df92dd980bf1964d4b34096d8627021c1dfc4'
$zipBytes = 708360885L
$exeSha = 'b8a91c564b10b774eace721440af54cf3958602e96f90a4535efea777554775f'
$base = 'https://github.com/marvoireflexai/MarVoiReflex/releases/download/v0.2.0-e2b-20261128/'
$hf = 'https://huggingface.co/google/gemma-4-E2B-it-qat-q4_0-gguf/resolve/main/'
$model = 'gemma-4-E2B_q4_0-it.gguf'
$modelSha = 'fa401b55b07ee70a54c6dae3903c783a6e65064312529ea57175cb5f8dec6634'
$projector = 'gemma-4-E2B-it-mmproj.gguf'
$projectorSha = '021059cce659fe7f9170d5599761d7bbaf644b798dab9503aca30dc43e6beb14'
$success = $false
$transcript = $false
function Test-Asset([string]$Path,[string]$Sha,[long]$Bytes=-1) {
    if(-not [IO.File]::Exists($Path)){return $false}
    $length=(Get-Item -LiteralPath $Path).Length
    if($length -le 0 -or ($Bytes -ge 0 -and $length -ne $Bytes)){return $false}
    return ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ieq $Sha)
}
function Fetch([string]$Url,[string]$Name,[string]$Sha,[long]$Bytes) {
    $target=Join-Path $cache $Name
    if(Test-Asset $target $Sha $Bytes){Write-Host ('已校驗快取：'+$Name);return $target}
    if(Test-Path -LiteralPath $target){Move-Item -LiteralPath $target -Destination ($target+'.invalid-'+$stamp)}
    $part=$target+'.partial'
    for($i=1;$i -le 3;$i++){
        try{
            if(Test-Path -LiteralPath $part){
                if(Test-Asset $part $Sha $Bytes){Move-Item -LiteralPath $part -Destination $target;return $target}
                if((Get-Item -LiteralPath $part).Length -ge $Bytes){Remove-Item -LiteralPath $part -Force}
            }
            Write-Host ('下載 '+$Name+' ('+$i+'/3)')
            $curl=Get-Command curl.exe -ErrorAction SilentlyContinue
            if($curl){
                $previous=$ErrorActionPreference
                try{$ErrorActionPreference='Continue'; & $curl.Source '--fail' '--location' '--retry' '2' '--connect-timeout' '30' '--continue-at' '-' '--output' $part $Url; $rc=$LASTEXITCODE}finally{$ErrorActionPreference=$previous}
                if($rc -ne 0){if($rc -eq 33 -or $rc -eq 36){if(Test-Path -LiteralPath $part){Remove-Item -LiteralPath $part -Force}};throw ('下載錯誤碼：'+$rc)}
            }else{
                $client=New-Object Net.WebClient
                try{$client.Headers['User-Agent']='MarVoiReflex-E2B/0.2.0';$client.DownloadFile($Url,$part)}finally{$client.Dispose()}
            }
            if(-not(Test-Asset $part $Sha $Bytes)){throw '下載大小或 SHA-256 不符'}
            Move-Item -LiteralPath $part -Destination $target
            Write-Host ('下載完整性通過：'+$Name)
            return $target
        }catch{
            Write-Host $_.Exception.Message -ForegroundColor Yellow
            if($i -eq 3){throw}
            Start-Sleep -Seconds 2
        }
    }
}
try{
    [void][IO.Directory]::CreateDirectory($root)
    $log=Join-Path $root ('install-'+$stamp+'.log')
    try{Start-Transcript -LiteralPath $log -Force | Out-Null;$transcript=$true}catch{}
    Write-Host 'MarVoiReflex | Gemma 4 E2B Vision | Windows x64'
    $arch=$env:PROCESSOR_ARCHITECTURE
    if($env:PROCESSOR_ARCHITEW6432){$arch=$env:PROCESSOR_ARCHITEW6432}
    if($arch -ne 'AMD64'){throw '此版本僅支援 Windows Intel / AMD x64。'}
    $pointer=Join-Path $root 'current.txt'
    if(Test-Path -LiteralPath $pointer){
        $old=Get-Content -LiteralPath $pointer -Raw -Encoding UTF8
        $old=$old.Trim()
        if($old -match '^MarVoiReflex-\d{8}-\d{6}-[0-9a-f]{6}$'){
            $existing=Join-Path $root $old
            $oldExe=Join-Path $existing 'MarVoiReflex.exe'
            $g=Join-Path $existing 'assets\gemma4-e2b'
            if((Test-Asset $oldExe $exeSha) -and (Test-Asset (Join-Path $g $model) $modelSha 3349516256L) -and (Test-Asset (Join-Path $g $projector) $projectorSha 986833664L) -and (Test-Path (Join-Path $g 'runtime\llama-server.exe')) -and (Test-Path (Join-Path $existing 'web\voice\index.html'))){
                Write-Host '現有安裝已通過校驗。'
                Start-Process -FilePath $oldExe -WorkingDirectory $existing
                $success=$true
                exit 0
            }
        }
    }
    $drive=New-Object IO.DriveInfo ([IO.Path]::GetPathRoot($root))
    if($drive.AvailableFreeSpace -lt 12GB){throw '需要至少 12GB 可用空間供下載及解壓縮。'}
    [void][IO.Directory]::CreateDirectory($cache)
    $zip=Fetch ($base+$zipName) $zipName $zipSha $zipBytes
    $m=Fetch ($hf+$model) $model $modelSha 3349516256L
    $v=Fetch ($hf+$projector) $projector $projectorSha 986833664L
    [void][IO.Directory]::CreateDirectory($stage)
    Write-Host '解壓縮 App 並放置 Gemma 4 E2B 權重。'
    [IO.Compression.ZipFile]::ExtractToDirectory($zip,$stage)
    $app=Join-Path $stage 'MarVoiReflex'
    $exe=Join-Path $app 'MarVoiReflex.exe'
    if(-not(Test-Asset $exe $exeSha)){throw '執行檔遺失、空白或校驗失敗。'}
    $g=Join-Path $app 'assets\gemma4-e2b'
    if(-not(Test-Path -LiteralPath (Join-Path $g 'runtime\llama-server.exe') -PathType Leaf)){throw 'CPU 推論引擎遺失。'}
    Copy-Item -LiteralPath $m -Destination (Join-Path $g $model)
    Copy-Item -LiteralPath $v -Destination (Join-Path $g $projector)
    if(-not(Test-Asset (Join-Path $g $model) $modelSha 3349516256L) -or -not(Test-Asset (Join-Path $g $projector) $projectorSha 986833664L)){throw '模型放置後校驗失敗。'}
    Move-Item -LiteralPath $app -Destination $final
    $finalExe=Join-Path $final 'MarVoiReflex.exe'
    if(-not(Test-Asset $finalExe $exeSha)){throw '最終 EXE 校驗失敗。'}
    [IO.File]::WriteAllText($pointer,[IO.Path]::GetFileName($final),(New-Object Text.UTF8Encoding($false)))
    Write-Host ('安裝完成：'+$final) -ForegroundColor Green
    Write-Host '正在啟動本機瀏覽器介面，首次模型載入請留意畫面狀態。'
    Start-Process -FilePath $finalExe -WorkingDirectory $final
    $success=$true
}catch{
    Write-Host ('安裝未完成：'+$_.Exception.Message) -ForegroundColor Red
    Write-Host '原有資料未覆寫。若裝置管理政策阻擋，請由管理員確認。'
}finally{
    if($success -and (Test-Path -LiteralPath $stage)){try{Remove-Item -LiteralPath $stage -Recurse -Force}catch{}}
    if($transcript){Write-Host ('記錄：'+$log);try{Stop-Transcript | Out-Null}catch{}}
}
if($success){exit 0}else{exit 1}
