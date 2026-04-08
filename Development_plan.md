
**Codex 開發計畫**：

**方案 1：`sadadYes/post-archiver-improved` 主方案**
它主打完整抓取 YouTube community posts，包含高畫質圖片、留言、錯誤處理、logging、rate limiting、資料驗證，整體更像可被自動化流程整合的元件。([GitHub][1])

**方案 2：`NothingNaN/YoutubeCommunityScraper` 備案方案**
它是非同步 scraper，輸出 JSON，欄位包含 `text_content`、`image_links`、`post_link`、`video_link`、`poll_content`，很適合做「抓資料 → 輸出 JSON → 給 n8n 發 Telegram」這種管線。([GitHub][2])

另外，n8n 的 Telegram node 支援 **Send Message**、**Send Photo**、**Send Media Group**，所以不只文字，單圖和多圖相簿都能送。([n8n Docs][3])
而 YouTube 官方 Data API 公開文件並沒有明確提供 Community posts 的正式穩定資源，所以這兩個方案本質上都屬於 scraping / reverse-engineering 路線。([Google for Developers][4])

---

# Codex 開發計畫

## 目標

建立一套可在主機上長期運行的流程：

**YouTube 頻道社群貼文 → 去重 → 圖片整理 → 傳送到 Telegram**

需求包含：

* 支援純文字貼文
* 支援單張圖片
* 支援多張圖片
* 避免重複發送
* 能被 n8n 方便呼叫
* 日後可替換抓取器，不動 n8n 主流程

---

## 最終架構

**抓取層**：Python wrapper
**編排層**：n8n
**通知層**：Telegram bot

流程：

`Schedule Trigger`
→ `Execute Command` 執行 Python wrapper
→ `Code` / `IF` 判斷貼文型別
→ `Telegram Send Message / Send Photo / Send Media Group`

---

## 方案 1：主方案

### 技術選型

以 `post-archiver-improved` 當抓取核心。它比 Selenium 類方案更適合當後端資料來源，因為 repo 描述就偏向結構化擷取與工程化處理，而不是單純瀏覽器模擬。([GitHub][1])

### 開發目標

做一個你自己的 wrapper，例如：

```bash
python yt_community_wrapper.py --channel https://www.youtube.com/@CHANNEL/community --limit 3
```

輸出固定 JSON：

```json
{
  "ok": true,
  "channel": "CHANNEL_NAME",
  "posts": [
    {
      "post_id": "abc123",
      "post_url": "https://www.youtube.com/post/abc123",
      "published_text": "2 hours ago",
      "text": "今晚 8 點直播",
      "images": [
        "https://....jpg"
      ],
      "video_links": [],
      "poll": null
    }
  ]
}
```

### Codex 任務拆解

1. 建立 Python 專案骨架
2. 安裝並封裝 `post-archiver-improved`
3. 寫 parser，把原始輸出轉成統一 JSON
4. 寫 `state.json` 或 SQLite 去重
5. 加上 exit code 規則

   * `0`：成功且有資料
   * `10`：成功但無新貼文
   * `20`：抓取失敗
6. 寫 logging
7. 提供給 n8n 的 CLI 介面

### n8n 串接方式

* **Execute Command**：跑 wrapper
* **IF**：判斷 `posts.length`
* **Switch**：

  * `images.length == 0` → Send Message
  * `images.length == 1` → Send Photo
  * `images.length > 1` → Send Media Group

### 優點

* 主功能最完整
* 適合正式部署
* 圖片支援較完整
* 後續擴充留言、投票較有空間。([GitHub][1])

### 風險

* 仍然是非官方抓取路線，YouTube 前端或內部結構變更時可能要修。([Google for Developers][4])

---

## 方案 2：備案方案

### 技術選型

以 `YoutubeCommunityScraper` 當抓取核心。它明確主打非同步、JSON 輸出、圖片連結和貼文連結抽取，適合快速做穩定的資料管線。([GitHub][2])

### 開發目標

做另一個 wrapper，例如：

```bash
python ypdl_wrapper.py --channel @CHANNEL --latest 3
```

輸出同一種 JSON schema，讓 n8n 不需要知道底層換了哪個 repo。

### Codex 任務拆解

1. 封裝 `yp-dl`
2. 將輸出 mapping 到統一 schema
3. 寫去重層
4. 寫錯誤處理與 timeout
5. 提供 `--json` 模式給 n8n

### 使用時機

* 主方案失效時快速切換
* 想先做 MVP
* 想先驗證 Telegram 圖文通知效果

### 優點

* JSON 導向
* 實作快速
* 好接 n8n。([GitHub][2])

### 風險

* 工程化程度可能不如主方案完整
* 同樣屬於非官方抓取。([GitHub][2])

---

## 統一資料介面設計

Codex 要先做這個，因為它能讓你未來替換抓取器時，不用重做 n8n。

### JSON Schema

```json
{
  "ok": true,
  "source": "post-archiver-improved",
  "channel": "string",
  "fetched_at": "2026-04-08T10:40:00+08:00",
  "posts": [
    {
      "post_id": "string",
      "post_url": "string",
      "text": "string",
      "images": ["string"],
      "video_links": ["string"],
      "published_text": "string",
      "is_members_only": false
    }
  ]
}
```

### 去重鍵

優先順序：

1. `post_id`
2. `post_url`
3. `text + first_image + published_text` 的 hash

---

## Telegram 訊息策略

### 無圖

用 **Send Message**

範例：

```text
📢 YouTube 社群更新

頻道：{{channel}}
內容：{{text}}

🔗 {{post_url}}
```

### 單圖

用 **Send Photo**，caption 帶文字。n8n 官方 Telegram node 支援這種操作。([n8n Docs][3])

### 多圖

用 **Send Media Group**。第一張帶 caption，其餘只帶圖片。n8n 官方文件列有 Send Media Group。([n8n Docs][3])

### fallback

如果圖連結失效：

* 自動退回 Send Message
* 訊息內附貼文連結

---

## 儲存與狀態管理

### MVP

先用本機 `state.json`

內容：

```json
{
  "last_seen_post_ids": [
    "abc123",
    "def456"
  ]
}
```

### 正式版

改 SQLite：

* `posts`
* `deliveries`
* `errors`

這樣可以：

* 避免重送
* 看歷史
* 做補發

---

## 測試計畫

### 單元測試

* parser 測試
* dedupe 測試
* schema 驗證測試

### 整合測試

* 模擬純文字貼文
* 模擬單圖貼文
* 模擬多圖貼文
* 模擬重複貼文
* 模擬圖片 URL 失效

### 驗收標準

* 新貼文只發一次
* 單圖貼文正確顯示圖片與 caption
* 多圖貼文用相簿送出
* 無圖貼文仍正常發送
* 抓取器失敗時，n8n 能記錄錯誤但不炸整個流程

---

## Codex 實作順序

### Phase 1：MVP

* 選 **方案 1**
* 做 wrapper
* 做 `state.json`
* 做純文字 + 單圖通知
* 先在 n8n 跑通

### Phase 2：完整通知

* 加多圖相簿
* 加 fallback
* 加 logging

### Phase 3：可替換架構

* 接入 **方案 2**
* 兩個抓取器共用同一 schema
* 增加 `--source primary|backup`

### Phase 4：正式部署

* systemd / cron
* SQLite
* 錯誤告警
* 監控最近一次成功抓取時間

---

## 給 Codex 的任務描述

你可以直接把這段丟給 Codex：

```text
建立一個 Python 專案，目標是抓取 YouTube Community posts，並輸出統一 JSON 給 n8n 使用。

需求：
1. 主抓取器使用 sadadYes/post-archiver-improved
2. 備用抓取器使用 NothingNaN/YoutubeCommunityScraper
3. 請實作 wrapper，輸出統一 schema：
   - ok
   - source
   - channel
   - fetched_at
   - posts[]
4. 每個 post 至少包含：
   - post_id
   - post_url
   - text
   - images[]
   - video_links[]
   - published_text
5. 加入去重機制，MVP 用 state.json
6. 提供 CLI：
   python app.py --source primary --channel <url> --limit 3 --json
7. 若無新貼文，回傳空陣列且 exit code 10
8. 若抓取失敗，exit code 20 並輸出錯誤 JSON
9. 結構化 logging
10. 補上 README，說明如何給 n8n Execute Command 使用

另外請提供：
- 測試假資料
- 單元測試
- 一個 sample n8n workflow 所需的輸出範例
```

---

## 最後定案

**我建議你就選這兩個：**

**主方案**：`sadadYes/post-archiver-improved`
**備案**：`NothingNaN/YoutubeCommunityScraper`  ([GitHub][1])

這樣最符合你現在的目標：
**先做出能抓貼文、能帶圖、能進 n8n、能送 Telegram，而且後面壞掉時有備援。**

我可以下一則直接把這份開發計畫改寫成 **更像你平常使用的 Codex prompt 版本**。

[1]: https://github.com/yt-dlp/yt-dlp/issues/11676?utm_source=chatgpt.com "Can this be a Method to scrape community posts that could ..."
[2]: https://github.com/NothingNaN/YoutubeCommunityScraper?utm_source=chatgpt.com "An asynchronous scraper for youtube community posts · ..."
[3]: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.telegram/?utm_source=chatgpt.com "Telegram node documentation"
[4]: https://developers.google.com/youtube/v3?utm_source=chatgpt.com "YouTube Data API"
