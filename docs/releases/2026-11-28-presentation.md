# MarVoiReflex v0.3.2｜成果展示與搜尋體驗

[Windows 安裝／更新工具](https://github.com/marvoireflexai/MarVoiReflex/releases/download/v0.3.2-presentation-20261128/MarVoiReflex-Download-Windows.cmd) ／ [成果展示啟動工具](https://github.com/marvoireflexai/MarVoiReflex/releases/download/v0.3.2-presentation-20261128/MarVoiReflex-Presentation.cmd)

既有 v0.3.1 標準安裝只需約 20.98 MB 更新包，保留 Gemma 權重與使用者資料。先完成安裝或更新並關閉原本 App，再執行成果展示啟動工具。

## 新增功能

- 每次啟動展示模式會建立獨立 session 與六份合成檔案（3 張圖片、PDF、TXT、CSV）；只索引該 session 的合成資料，禁止擴及本機磁碟。不掃描私人檔案，不覆寫其他 session。
- 展示圖片採無語意檔名，搜尋仍經由實際 Gemma 4 E2B Vision 推論，並非預先設定答案。
- 圖片結果卡依可視範圍載入縮圖，保留原檔開啟與下載。
- 明確檔案任務可由一般文字聊天模式直接路由；加入常見口語清單查詢。
- 展示啟動工具只啟動經校驗的新版 EXE，不重新下載權重；若有既有 App 正在執行則提示先關閉，避免兩套模型同時占用記憶體。
- 附可重複執行的 14 項隔離驗收腳本及現場展示檢查清單。

## 實測

| 項目 | 封裝版結果 |
|---|---|
| 14 項補充展示驗收 | 14/14 |
| 服務啟動 | 4.70 秒 |
| 六項基本索引請求 | 4–28 毫秒 |
| 三項首次圖片內容搜尋（每次 3 張候選） | 14.20–19.77 秒 |
| 重複汽車圖片搜尋 | 8.51 秒 |
| 程序樹 RSS 單次快照 | 3882.1 MiB |
| 原始素材雜湊 | 皆一致 |
| JavaScript 錯誤 | 0 |

Windows x64 32GB 桌機、CPU-only；數據僅限六份合成素材的受控實測，基本索引時間不含啟動與索引建立；RSS 為快照而非峰值。不代表真實商業圖庫準確率、8GB 實機、真人語音或原訂 50 組研究案例已完成。語音直接交辦沿用 v0.3.1 功能，本輪並未重驗實體麥克風。

[實測證據](../evidence/presentation-readiness-20261128.json) ／ [成果發表驗收計畫](../presentation-readiness.md) ／ [使用指南](../user-guide.md)
