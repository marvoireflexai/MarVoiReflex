# Local Voice Pipeline｜多引擎架構

狀態：原始碼整合與 Windows CPU 開發環境測試完成；v0.3.0 標準 Windows 安裝包提供基礎離線引擎及本機搜尋，選用 Moonshine、OCR、向量權重仍須另行配置。本頁不將開發環境測試等同跨裝置驗收。

## 架構與啟用方式

- 預設保留 Gemma 4 E2B Vision、Faster Whisper Small INT8、Windows SAPI 及本機 MCP。沒有 API Key 或雲端推論需求。
- Moonshine Mandarin Tiny Streaming：選用的本機快速語音引擎，安裝後優先提供增量轉錄與最終辨識；任務轉錄以 Whisper 複核，不一致時列出替代文字，使用者確認後才交辦。Silero VAD 過濾無語音的片段，語音引擎不可用時保留 Whisper。
- E4B：選用的本機進階文字模型；複雜對話及任務解析重試可經過進階端點。端點僅允許 127.0.0.1 HTTP，失敗回退至 E2B；模型沒有直接操作檔案的權限。
- 回覆語音：第一句完成合成即可播放，其餘句子由前端預取。取消會使後續分段失效。目前合成引擎仍為 Windows SAPI；此處為分段合成，不是 LLM token streaming，也不是神經 TTS。
- 素材索引：在任務頁輸入「建立素材索引」或「更新素材索引」，每次最多新增 40 張。SQLite 按檔案 SHA-256 儲存描述、選用 OCR 文字與 EmbeddingGemma 向量。向量排序僅決定搜尋順序，不移除候選，也不授權任何檔案修改。圖片搜尋的確定結果另有本機持久化快取。

## 開發環境設定

請先依 README 的開發環境指引完成 v0.2.1 執行資產設定。以下命令以 Python 3.12 開發環境執行，並將路徑替換為自己的目錄。

1. 選用快速語音：安裝 requirements-voice-optional.txt，再執行 scripts/setup_moonshine.py --app-root 完整App目錄 --cache-root 下載快取目錄。也可用 MARVOI_MOONSHINE_DIR 指定已下載的 Tiny Streaming 中文權重資料夾。僅明確執行安裝程序才會下載；運行中的 App 不會下載。
2. 選用進階模型：從 Google 官方 E4B QAT GGUF 儲存庫下載 gemma-4-E4B_q4_0-it.gguf（5,154,941,280 bytes）。執行 scripts/start_advanced_model.py --runtime llama-server.exe完整路徑 --model GGUF完整路徑。啟動器會核對 SHA-256 與 RAM。預設埠 18787；啟動 App 前將 MARVOI_ADVANCED_URL 設為 http://127.0.0.1:18787。建議 24 GiB RAM；低記憶體裝置使用 E2B 即可。
3. 選用素材索引：安裝 requirements-index-optional.txt；執行 scripts/setup_embedding.py --app-root 完整App目錄 --cache-root 下載快取目錄，或設定 MARVOI_EMBEDDING_DIR 指向已下載的 EmbeddingGemma Q4 權重。設定 MARVOI_OCR=1 啟用 RapidOCR ONNX Runtime。缺少選用元件時保留基本描述索引及既有視覺搜尋。

## 實際驗證

- 新語音及模型流程：11/11 項來源程式整合測試，包含 E4B CPU 啟動、實際 E2B/E4B 路由、故障回退、增量轉錄、雙引擎審閱、靜音辨識拒絕、分段語音、取消及圖片搜尋快取。
- Moonshine 單獨辨識三組合成中文語句：0.041–0.068 秒，忽略標點後字元錯誤率 0%。完整雙引擎複核時間為 5.251–6.721 秒，並非即時對話延遲。
- 素材索引 4/4，OCR 讀取測試圖片「春季優惠 SALE」，768 維向量；第二次索引未新增重複紀錄。
- 尚未驗證真實麥克風、噪音、8GB 裝置、瀏覽器端分段播放的實際聆聽體驗、大規模真實圖庫，以及新的免安裝 Windows 封裝。Pocket TTS 中文模型及其他神經 TTS 尚未整合。

## 上游元件與授權

- Moonshine Voice 0.1.6： https://github.com/moonshine-ai/moonshine ，新版 Mandarin Tiny Streaming 權重依上游文件為 MIT；不使用受非商用限制的舊版中文 Base 模型。請查閱具體下載版本授權。
- Faster Whisper / Silero： https://github.com/SYSTRAN/faster-whisper
- Google Gemma 4 E4B： https://huggingface.co/google/gemma-4-E4B-it-qat-q4_0-gguf
- Google EmbeddingGemma： https://huggingface.co/google/embeddinggemma-300m
- RapidOCR： https://github.com/RapidAI/RapidOCR
- 測試證據：[local-voice-pipeline-20261128.json](evidence/local-voice-pipeline-20261128.json)
