# Windows 使用指南｜Gemma 4 E2B Vision

**[下載 Windows 一鍵安裝／啟動工具](https://github.com/marvoireflexai/MarVoiReflex/releases/download/v0.2.1-task-fix-20261128/MarVoiReflex-Download-Windows.cmd)** ／ [新版發行頁面](https://github.com/marvoireflexai/MarVoiReflex/releases/tag/v0.2.1-task-fix-20261128)

此版本預設使用 Gemma 4 E2B IT QAT Q4_0 及視覺 projector。首次需下載 App、3.35 GB 語言權重和 0.99 GB 視覺權重，合計約 5.06 GB（含任務修正包）。模型由 Google 官方來源下載，校驗 SHA-256 後放置到正確位置。無需 GitHub 帳號、API Key、獨顯、另外安裝 Python 或 Node.js。

1. 下載並雙擊 MarVoiReflex-Download-Windows.cmd。
2. 下載完成會自動開啟本機瀏覽器介面。再次雙擊工具可啟動現有安裝。從 v0.2.0 更新時請先關閉 App，再執行新版工具；已安裝的模型與使用者資料會保留。
3. 進入任務模式，按新增素材匯入 PNG／JPEG／WebP 或 TXT／MD。
4. 輸入「找出有汽車的照片」或「找出紅色背景的素材」來搜尋圖片內容，無須依靠檔名。
5. 要依檔案類型整理時，輸入「整理全部圖片，先給我預覽」，核對計畫並按確認。

語音任務辨識後會將轉錄送入任務輸入框；確認或修改文字後再送出。圖片搜尋的複核結果不一致時會列為需確認。

## 環境與限制

- Windows 10/11 x64，建議至少預留 12 GB 磁碟空間。CPU 模式、4 執行緒，4096 context。
- 本機 UI 使用 Chrome／Edge 等現代瀏覽器；避免原生 WebView2 白畫面。原生視窗為選用的 --native 模式。
- 語音辨識使用 faster-whisper small INT8；朗讀須有 Windows 中文 SAPI 語音。
- 圖片內容搜尋單次最多 40 張；不支援指定路徑或複合日期條件。辨識結果不會自動搬移檔案。
- 32GB 桌機的驗證結果尚不能代表 8GB 記憶體裝置、其他硬體配置及受管理的 Windows 環境之相容性。受管理電腦須遵守管理員的執行及網路政策。

App 安裝在使用者的 LocalAppData 下 MarVoiReflex/20261128-E2B，資料在各安裝目錄的 Data-MarVoiVoice；舊安裝不會被覆寫。若網路受限，請檢查安裝日誌並聯絡管理員。不要公開 connection.json（含本機連線權杖）。

## 手動下載

下方完整 ZIP 為 v0.2.0 基礎安裝包；建議優先使用 v0.2.1 一鍵工具，會自動套用修正並校驗。手動安裝基礎版後，若非標準安裝目錄，需將 v0.2.1 修正包內 files/ 的 4 個檔案依原相對路徑套用；操作前先關閉 App、備份原始程式檔並核對 SHA-256，勿覆蓋使用者資料。

1. 從 [基礎發行頁面](https://github.com/marvoireflexai/MarVoiReflex/releases/tag/v0.2.0-e2b-20261128) 下載 MarVoiReflex-Gemma4-E2B-Windows-x64.zip 並完整解壓。
2. 從 [Google 官方 Gemma 4 E2B QAT GGUF](https://huggingface.co/google/gemma-4-E2B-it-qat-q4_0-gguf) 下載 gemma-4-E2B_q4_0-it.gguf 及 gemma-4-E2B-it-mmproj.gguf。
3. 將兩個檔案放入 MarVoiReflex/assets/gemma4-e2b，保留 runtime 子資料夾及其他所有檔案。
4. 雙擊 MarVoiReflex.exe。

完整校驗碼、版本限制與驗證結果見[本次發行紀錄](releases/2026-11-28-task-fix.md)。舊版 MiniCPM5-2B 僅作為[歷史版本](releases/2026-10-31.md)保留。
