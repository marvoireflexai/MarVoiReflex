# Gemma 4 E2B 圖片內容搜尋實驗（2026-11-28）

本頁保存 2026-11-28 初期 E2B 原始碼實驗的設定與測試證據。新版下載與完整發行測試狀態見[發行紀錄](releases/2026-11-28.md)。

## 執行環境

- Windows x64、Python 3.12，已具備原版 App 的 MCP、語音等執行資產。
- Google 官方 Gemma 4 E2B IT QAT Q4_0 GGUF，3,349,516,256 bytes，SHA-256 fa401b55b07ee70a54c6dae3903c783a6e65064312529ea57175cb5f8dec6634。
- 官方視覺 projector，986,833,664 bytes，SHA-256 021059cce659fe7f9170d5599761d7bbaf644b798dab9503aca30dc43e6beb14。
- llama.cpp b12823 Windows CPU x64，4 CPU threads、4096 context、無 GPU offload。
- 權重來源：https://huggingface.co/google/gemma-4-E2B-it-qat-q4_0-gguf
- 推論引擎：https://github.com/ggml-org/llama.cpp/releases/tag/b12823

設定環境變數 MARVOI_MODEL_PROFILE=gemma4-e2b-vision，MARVOI_GEMMA_ROOT 指向含上述兩個 GGUF、runtime/llama-server.exe 與對應 DLL 的資料夾。MARVOI_ASSETS_ROOT 則指向原版 App 完整執行資產的根目錄。仍需依原版開發指引安裝依賴，Pillow 用於圖片讀取。使用隔離資料目錄測試，避免改動既有工作區。

## 操作範圍

在交辦模式匯入圖片後，使用「找出有汽車的照片」、「找出紅色背景的素材」或「依圖片內容搜尋……」。實驗版只搜尋授權工作區內已匯入的圖片，單次最多 40 張，逐張辨識，按相同內容雜湊及查詢文字提供本次程序的快取。檔名不會送入模型。不會搬移、刪除、修改檔案。不支援日期、指定路徑或複合分類任務。

## 驗證

32GB RAM Windows 桌機的獨立模型與搜尋模組已實測。6 個圖像判斷用例通過（第二輪提示）；三組自然語言搜尋用例通過，使用三張合成圖及故意不符的檔名。逐張辨識約 2.3–2.8 秒；每次搜尋三張約 7.8–8.0 秒。

此證據不等同完整 App UI、語音、原本 MCP 服務、重新打包 EXE、8GB 或網咖相容性驗收。真實商業圖片、細小文字、品牌辨識、大量資料與語意索引仍待驗證。

證據檔：evidence/gemma4-e2b-vision-20261128.json
