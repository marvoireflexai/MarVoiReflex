@echo off
setlocal
chcp 65001 >nul
set "MVR_DEMO_LAUNCHER=%~f0"
powershell.exe -NoLogo -NoProfile -Command "$ErrorActionPreference='Stop'; $s=Get-Content -LiteralPath $env:MVR_DEMO_LAUNCHER -Raw -Encoding UTF8; $m='# MVR_PRESENTATION_PS'; & ([scriptblock]::Create($s.Substring($s.LastIndexOf($m))))"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
# MVR_PRESENTATION_PS
$ErrorActionPreference='Stop'
try{
    $root=Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MarVoiReflex\20261128-E2B'
    $short=Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'MVR'
    $pointer=Join-Path $root 'current.txt'
    if(-not [IO.File]::Exists($pointer)){throw '請先執行 v0.3.2 安裝／更新工具。'}
    $id=(Get-Content -LiteralPath $pointer -Raw -Encoding UTF8).Trim()
    if($id -match '^a-[0-9a-f]{8}$'){$dir=Join-Path $short $id}
    elseif($id -match '^MarVoiReflex-\d{8}-\d{6}-[0-9a-f]{6}$'){$dir=Join-Path $root $id}
    else{throw '安裝記錄不正確，請重新執行更新工具。'}
    $exe=Join-Path $dir 'MarVoiReflex.exe'
    foreach($item in @($root,$dir,$exe)){if((Get-Item -LiteralPath $item -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw '不允許連結安裝路徑。'}}
    if((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ine '6ee6d6d7aba2a8f220b96ad20e3ab4d30e3f9f9d2809636961f58390bb096f6c'){throw '請先更新至 v0.3.2。'}
    if(Get-Process -Name MarVoiReflex -ErrorAction SilentlyContinue){throw '請先關閉正在執行的 MarVoiReflex，以免兩個本機模型同時占用記憶體。'}
    Write-Host '成果展示模式：建立全新隔離的合成素材，不讀取個人磁碟。'
    Start-Process -FilePath $exe -ArgumentList '--presentation' -WorkingDirectory $dir
    exit 0
}catch{Write-Host $_.Exception.Message -ForegroundColor Red;exit 1}
