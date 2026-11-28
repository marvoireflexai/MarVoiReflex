# MarVoiReflex macOS Preview

目標：macOS 14 以上，Apple Silicon ARM64 與 Intel x86_64 原生封裝。基於 v0.3.3 的 CPU 推論架構，Windows 發行版不受影響。

## 下載及使用

兩種架構分別驗收，只有該架構的原生 GitHub Actions 建置及凍結程式測試通過才會發布對應 macOS 預覽版，請查看 [GitHub Releases](https://github.com/marvoireflexai/MarVoiReflex/releases) 及 [macOS Actions](https://github.com/marvoireflexai/MarVoiReflex/actions/workflows/macos-preview.yml)。在「關於這台 Mac」確認 Apple 晶片或 Intel，下載對應 ZIP，完整解壓後保留 .app、assets、web 與 .command 在同一資料夾。先執行 MarVoiReflex-Install.command，從 Google 官方來源下載約 4.34 GB 權重並校驗 SHA-256，成功後啟動本機瀏覽器介面。首次下載後再次執行工具沿用模型。需保留足夠儲存空間。預覽包為 ad-hoc 簽署，尚未 Developer ID 簽署或 Apple 公證；遵循系統安全提示，不要求停用 Gatekeeper。不需要 sudo、API Key 或 Windows 虛擬機。

## 功能與差異

- Gemma 4 E2B Vision、faster-whisper Small INT8、本機 MCP、圖片內容檢索、任務進度與取消、原檔取得。
- macOS 使用系統 say 及 afconvert 分段合成音訊；需要已安裝的中文系統語音。瀏覽器負責麥克風授權。
- Finder 顯示原始位置與原檔開啟；本機搜尋限明確授權的 Desktop、Downloads、Documents、Pictures、Movies、Music。尊重 macOS TCC，不要求完整磁碟存取，不掃描其他帳號或掛載磁碟。
- 使用者資料位於 ~/Library/Application Support/MarVoiReflex/data；外部原檔唯讀。工作區搬移使用 Darwin 原子不覆寫操作及確認機制。
- 成果展示模式使用 MarVoiReflex-Presentation.command，建立隔離合成素材；先關閉一般模式並完成權重下載。
- 首版保留 CPU 路徑；低於 10 GiB 記憶體採較低的圖片 token 上限（280）及較小模型快取，可能影響細節辨識；，Metal、Moonshine、E4B、OCR、向量模型未隨標準 Mac 包交付。建議 16GB RAM，8GB 實體裝置未驗證。macOS 最低版本及真實裝置相容性待實機驗收。

## 建置

在原生 macOS Python 3.12 環境安裝 requirements-macos.txt，執行 python scripts/build_macos.py。腳本校驗 llama.cpp、Node、Whisper 與 Google 權重，使用 PyInstaller 產出架構專屬 .app；凍結程式測試完成才建立 ZIP，Gemma 權重不包含在 ZIP 內。CI 生成原生 macOS 測試證據，不以 Windows 測試替代 macOS 驗收。

## 首輪驗證紀錄

原始碼 3ba4b4a：Intel 原生 macOS 15.7.9 9/9 通過；ARM64 啟動、索引及基本查詢通過，但圖片推論逾時。首輪建置未公開發行。第二輪更新 PyAV 至 18.1.1，獨立發布兩個架構，保留 ARM64 診斷資訊並調整低記憶體設定。是否可下載以各架構驗收及實際 Release 為準。
