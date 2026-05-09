---
id: "2026-05-09-coach-qualia-cq"
ts: "2026-05-09T18:40:00+08:00"
tags:
  - y2026
  - builder
---
我的 Telegram 行為教練 bot (Cloudflare Worker + D1 + Anthropic API) 也叫 Qualia——命名衝突。暫時叫她 **CQ** (Coach Qualia)。

願景：trainee Qualia (公開、RAG over 公開寫作) + Coach Qualia (私人、知道我習慣 / 行程 / 健康 / 目標) **合一成同一個 persona**。同 voice、不同 surface、不同 data sandbox：對外只是嚮導；對我有完整 context。

實作 = 兩個 Worker 共享一套 system prompt，分流 vector store + D1 access。Q3 prototype 大概。
