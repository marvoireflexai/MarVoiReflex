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
$installRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MVR'
$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,6)
$shortId = [Guid]::NewGuid().ToString('N').Substring(0,8)
$stage = Join-Path $installRoot ('s-' + $shortId)
$final = Join-Path $installRoot ('a-' + $shortId)
$zipName = 'MarVoiReflex-Gemma4-E2B-Windows-x64.zip'
$zipSha = '43e06d091651cecfb164b246a86df92dd980bf1964d4b34096d8627021c1dfc4'
$zipBytes = 708360885L
$baseExeSha = 'b8a91c564b10b774eace721440af54cf3958602e96f90a4535efea777554775f'
$priorExeSha = '94b7fcfcd768dcc6c556833098f28d96ae0b6c541c6cc2db758159b9475706b9'
$localSearchExeSha = 'c82409dda8b3e04aa02f9a9d3e897f524dfe7ff077ccb4f034c34801d20cc74a'
$exeSha = '76d20fbb62db2bc2b5751b05892fbacf75750166b8d5b289ec714e976500636d'
$base = 'https://github.com/marvoireflexai/MarVoiReflex/releases/download/v0.2.0-e2b-20261128/'
$hf = 'https://huggingface.co/google/gemma-4-E2B-it-qat-q4_0-gguf/resolve/main/'
$patchBase = 'https://github.com/marvoireflexai/MarVoiReflex/releases/download/v0.3.1-direct-voice-20261128/'
$patchName = 'MarVoiReflex-Direct-Voice-Files-Windows-x64.zip'
$patchSha = '42ca1f8f49800dd9a09b28493f3c06a0b74350db21b7009cf871e303f7deb999'
$patchBytes = 20976708L
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

$patchFiles = @(
    [pscustomobject]@{path='MarVoiReflex.exe';size=15304705L;sha256='76d20fbb62db2bc2b5751b05892fbacf75750166b8d5b289ec714e976500636d';old_sha256=@('94b7fcfcd768dcc6c556833098f28d96ae0b6c541c6cc2db758159b9475706b9','b8a91c564b10b774eace721440af54cf3958602e96f90a4535efea777554775f','c82409dda8b3e04aa02f9a9d3e897f524dfe7ff077ccb4f034c34801d20cc74a');allow_absent=$false},
    [pscustomobject]@{path='voice_runtime/base_library.zip';size=1332808L;sha256='0d33758b2161b323c8ef568e35397d5c921372ee9fdd484100cd330bbece2687';old_sha256=@('73357d404c0b934b43ba4d003132bf1fde2c6da1c7f2db8648805b2b034f6582','772e5da6ba515e7dcbee7c039ffcb9fa1d8a491f7f96501772786498e98c81eb','c591cf873f32ce28e7dc6d9f207163cf83274751a4eaa0dc48f99a3ee9229db5');allow_absent=$false},
    [pscustomobject]@{path='web/voice/index.html';size=7349753L;sha256='6f857ae183527ce7fda403c38ca60d394f88b40f0a1a3fa87ca8100606fd52a2';old_sha256=@('14115b10e78f1045e67c3d48c11d02284a6a9e5743d7ff013b7f323d56c5f7f5','a7ce7fc95e47d78e0e9f78c4caccca0bff7e0acab52ab9cfa6ea0fa564e0de35','c44a6f08f6fa467da519599086f5327d845cda1bde469bd9dbca4f4c87e63252');allow_absent=$false},
    [pscustomobject]@{path='web/voice/live.js';size=34372L;sha256='d3e33fb41632b1263ae107efeadeb46272725e0b20462b9e06d07647ab4f6607';old_sha256=@('c7ddc4084cefa656ff3c4618ca73a3cc39ae0b51c58698de2f6496aee4aa9a93','cf55635cf968ab5dc131cb13b777839d07fb8342fd98a59c0a39cde0cdc4f757','ecfbbda82425bb8dfc1656243bbb154825a5f4e1f557caf4f27828b3af57a8cc');allow_absent=$false}
)
function Assert-RegularPath([string]$Path,[string]$Root) {
    $full=[IO.Path]::GetFullPath($Path)
    $bound=[IO.Path]::GetFullPath($Root).TrimEnd('\')+'\'
    if(-not $full.StartsWith($bound,[StringComparison]::OrdinalIgnoreCase)){throw '更新路徑超出安裝目錄。'}
    $cursor=$full
    while($cursor.StartsWith($bound,[StringComparison]::OrdinalIgnoreCase)){
        if(Test-Path -LiteralPath $cursor){
            $item=Get-Item -LiteralPath $cursor -Force
            if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw '不允許更新連結或重新解析路徑。'}
        }
        $cursor=[IO.Path]::GetDirectoryName($cursor)
    }
    if((Get-Item -LiteralPath $Root -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw '安裝目錄不可為連結。'}
}
function Test-PatchCurrent([string]$App) {
    foreach($f in $patchFiles){
        $dest=Join-Path $App $f.path
        Assert-RegularPath $dest $App
        if(-not(Test-Asset $dest $f.sha256 $f.size)){return $false}
    }
    return $true
}
function Apply-LocalPatch([string]$App){
    if(Test-PatchCurrent $App){Write-Host '語音交辦及檔案取得版本已校驗。';return}
    $appExe=Join-Path $App 'MarVoiReflex.exe'
    if(-not((Test-Asset $appExe $baseExeSha) -or (Test-Asset $appExe $priorExeSha) -or (Test-Asset $appExe $localSearchExeSha) -or (Test-Asset $appExe $exeSha))){throw '原始版本不相容，請重新安裝。'}
    foreach($proc in @(Get-Process -Name MarVoiReflex -ErrorAction SilentlyContinue)){
        if(-not $proc.Path -or [string]::Equals($proc.Path,$appExe,[StringComparison]::OrdinalIgnoreCase)){throw '請先關閉 MarVoiReflex 及本機介面，再重新執行更新工具。'}
    }
    [void][IO.Directory]::CreateDirectory($cache)
    $archive=Fetch ($patchBase+$patchName) $patchName $patchSha $patchBytes
    $patchDir=Join-Path $root ('patch-stage-'+$stamp)
    $backupDir=Join-Path $root ('patch-backup-'+$stamp)
    [void][IO.Directory]::CreateDirectory($patchDir)
    [IO.Compression.ZipFile]::ExtractToDirectory($archive,$patchDir)
    $pending=@()
    foreach($f in $patchFiles){
        $dest=Join-Path $App $f.path
        $src=Join-Path (Join-Path $patchDir 'files') $f.path
        Assert-RegularPath $dest $App
        if(-not(Test-Asset $src $f.sha256 $f.size)){throw '修正檔案完整性校驗失敗。'}
        if(Test-Asset $dest $f.sha256 $f.size){continue}
        $existed=[IO.File]::Exists($dest)
        if($existed){
            $oldHash=(Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant()
            if($f.old_sha256 -notcontains $oldHash){throw ('原始檔案曾變更，已停止更新：'+$f.path)}
        }elseif(-not $f.allow_absent){throw ('原始檔案遺失，已停止更新：'+$f.path)}
        $backup=Join-Path $backupDir $f.path
        if($existed){
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($backup))
            Copy-Item -LiteralPath $dest -Destination $backup
        }
        $pending+=@([pscustomobject]@{dest=$dest;src=$src;backup=$backup;expected=$f.sha256;size=$f.size;existed=$existed})
    }
    $replaced=@()
    try{
        foreach($item in $pending){
            $replaced+=@($item)
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($item.dest))
            Assert-RegularPath $item.dest $App
            Copy-Item -LiteralPath $item.src -Destination $item.dest -Force
            if(-not(Test-Asset $item.dest $item.expected $item.size)){throw '套用修正後校驗失敗。'}
        }
        if(-not(Test-PatchCurrent $App)){throw '修正版本未完整安裝。'}
    }catch{
        foreach($item in $replaced){try{if($item.existed){Copy-Item -LiteralPath $item.backup -Destination $item.dest -Force}elseif(Test-Path -LiteralPath $item.dest){Remove-Item -LiteralPath $item.dest -Force}}catch{Write-Host ('還原失敗，備份位於：'+$item.backup) -ForegroundColor Red}}
        throw
    }
    Write-Host '已更新語音交辦與直接取得檔案功能；既有素材、模型及使用者資料均保留。' -ForegroundColor Green
}

try{
    [void][IO.Directory]::CreateDirectory($root)
    [void][IO.Directory]::CreateDirectory($installRoot)
    foreach($folder in @($root,$installRoot)){
        if((Get-Item -LiteralPath $folder -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw '安裝或快取目錄不可為連結。'}
    }
    $log=Join-Path $root ('install-'+$stamp+'.log')
    try{Start-Transcript -LiteralPath $log -Force | Out-Null;$transcript=$true}catch{}
    Write-Host 'MarVoiReflex 0.3.1 | Installer r2 | Windows x64'
    $arch=$env:PROCESSOR_ARCHITECTURE
    if($env:PROCESSOR_ARCHITEW6432){$arch=$env:PROCESSOR_ARCHITEW6432}
    if($arch -ne 'AMD64'){throw '此版本僅支援 Windows Intel / AMD x64。'}
    $pointer=Join-Path $root 'current.txt'
    if(Test-Path -LiteralPath $pointer){
        $old=Get-Content -LiteralPath $pointer -Raw -Encoding UTF8
        $old=$old.Trim()
        $existing=$null
        if($old -match '^MarVoiReflex-\d{8}-\d{6}-[0-9a-f]{6}$'){$existing=Join-Path $root $old}
        elseif($old -match '^a-[0-9a-f]{8}$'){$existing=Join-Path $installRoot $old}
        if($existing -and (Test-Path -LiteralPath $existing -PathType Container)){
            $oldExe=Join-Path $existing 'MarVoiReflex.exe'
            $g=Join-Path $existing 'assets\gemma4-e2b'
            if(((Test-Asset $oldExe $baseExeSha) -or (Test-Asset $oldExe $priorExeSha) -or (Test-Asset $oldExe $localSearchExeSha) -or (Test-Asset $oldExe $exeSha)) -and (Test-Asset (Join-Path $g $model) $modelSha 3349516256L) -and (Test-Asset (Join-Path $g $projector) $projectorSha 986833664L) -and (Test-Path (Join-Path $g 'runtime\llama-server.exe')) -and (Test-Path (Join-Path $existing 'web\voice\index.html'))){
                Apply-LocalPatch $existing
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
    # Preflight the exact archive paths before touching the installation.
    $archive=[IO.Compression.ZipFile]::OpenRead($zip)
    try{
        foreach($entry in $archive.Entries){
            $rel=$entry.FullName.Replace('/','\')
            if(-not $rel.StartsWith('MarVoiReflex\',[StringComparison]::Ordinal) -or $rel.Contains(':') -or ($rel.Split('\') -contains '..')){throw '安裝壓縮檔包含非預期路徑。'}
            $dest=[IO.Path]::GetFullPath((Join-Path $stage $rel))
            $installed=[IO.Path]::GetFullPath((Join-Path $final $rel.Substring('MarVoiReflex\'.Length)))
            if($dest.Length -ge 260 -or $installed.Length -ge 260 -or [IO.Path]::GetDirectoryName($dest).Length -ge 248){throw '此帳號的安裝路徑仍過長，請使用較短的本機使用者資料路徑。下載快取已保留。'}
        }
    }finally{$archive.Dispose()}
    if((Test-Path -LiteralPath $stage) -or (Test-Path -LiteralPath $final)){throw '安裝目錄名稱衝突，請重新啟動工具。'}
    [void][IO.Directory]::CreateDirectory($stage)
    Write-Host ('解壓縮至短路徑：'+$stage)
    [IO.Compression.ZipFile]::ExtractToDirectory($zip,$stage)
    $app=Join-Path $stage 'MarVoiReflex'
    $exe=Join-Path $app 'MarVoiReflex.exe'
    if(-not(Test-Asset $exe $baseExeSha)){throw '執行檔遺失、空白或校驗失敗。'}
    $g=Join-Path $app 'assets\gemma4-e2b'
    if(-not(Test-Path -LiteralPath (Join-Path $g 'runtime\llama-server.exe') -PathType Leaf)){throw 'CPU 推論引擎遺失。'}
    Copy-Item -LiteralPath $m -Destination (Join-Path $g $model)
    Copy-Item -LiteralPath $v -Destination (Join-Path $g $projector)
    if(-not(Test-Asset (Join-Path $g $model) $modelSha 3349516256L) -or -not(Test-Asset (Join-Path $g $projector) $projectorSha 986833664L)){throw '模型放置後校驗失敗。'}
    Apply-LocalPatch $app
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
