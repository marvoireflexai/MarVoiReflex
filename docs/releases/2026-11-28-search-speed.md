# MarVoiReflex v0.3.3｜圖片搜尋反應速度

[Windows 安裝／更新工具](https://github.com/marvoireflexai/MarVoiReflex/releases/download/v0.3.3-search-speed-20261128/MarVoiReflex-Download-Windows.cmd) ／ [成果展示啟動工具](https://github.com/marvoireflexai/MarVoiReflex/releases/download/v0.3.3-search-speed-20261128/MarVoiReflex-Presentation.cmd)

既有 v0.3.2 標準安裝僅需約 20.99 MB 更新包，保留模型及使用者資料。

## 變更

- 圖片判斷使用受約束的 yes/no/uncertain 單欄位輸出，避免小型模型在說明欄位重複生成。正向結果保留第二次獨立複核，判斷不一致仍列為需確認。
- 以圖片內容雜湊及查詢條件重用有效判定；相同條件尾端一般標點的差異不再導致重算。有效的不確定結果僅在工作階段記憶體重用；不計為確定命中。錯誤或未完成的複核不快取。
- 任務與通話頁顯示真實已辨識、符合及重用數量，可停止搜尋。當前模型請求返回後停止後續候選；不取消已確認搬移。取消保留原輸入文字。
- 既有模型、語音引擎、檔案權限及原檔下載方式不變。外部檔案仍採唯讀，圖片判斷快取留於本機記憶體。
- 可重跑的測試及方法：[搜尋反應速度驗證](../testing/search-responsiveness.md)。

## 實測（同一小型展示資料集，Windows x64 32GB CPU 桌機）

| 指標 | v0.3.2 封裝版 | v0.3.3 封裝版 |
|---|---:|---:|
| 首次汽車圖片搜尋（3 張） | 19.77 秒 | 11.64 秒 |
| 重複汽車圖片搜尋 | 8.51 秒 | 0.076 秒 |
| 首次紅色背景搜尋 | 14.20 秒 | 11.52 秒 |
| 首次黃色花朵搜尋 | 19.26 秒 | 11.51 秒 |
| 搜尋取消反應 | 未測 | 2.97 秒 |

原始碼及更新後封裝版各通過 6/6 項驗收，包含實際 E2B 圖片搜尋、快取、進度、取消、重試及逐位元組原檔下載。原始資料雜湊保持一致、無 JavaScript 錯誤。另通過取消權限與過期 ID 單元測試。

數據為個別受控樣本，並非統計性速度或準確率估計。重複查詢依賴同工作階段快取，首次搜尋仍需模型推論；未涵蓋真人語音、真實商業圖庫、8GB 實機或全磁碟效能。原訂 50 組研究案例仍需完成。

[完整證據](../evidence/search-responsiveness-20261128.json) ／ [發表驗收計畫](../presentation-readiness.md)
