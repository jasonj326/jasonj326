# Long Game data

> Single source of truth for `/long-game/` and `/zh/long-game/`.
> Edit cells → commit + push → pages auto-update on next load.
> Empty cells: leave blank (do not write `0` or `-`).
> Bilingual columns (`*_en`, `*_zh`): each page picks its own language.

# Long Game

Quest Objective
Help people and get rich: Looking for wonderfully odd people with stories.
助人、變富足：找奇特有故事的靈魂

Challenge Accepted

Current Status
Irrationally optimistic 
非理性樂觀者
## Wayfarer axes

> `lv` auto-derived from `value` via per-axis ceiling thresholds (see ladder block in `/long-game/`). You only edit `value`.

| axis   | value | unit | formula                                |
| ------ | ----- | ---- | -------------------------------------- |
| cardio | 110   | pts  | running + swim×10 km / year + biking/4 |
| mind   | 36    | pts  | meditation days / year                 |
| force  | 20    | pts  | approx. strength sessions / year       |
| rest   | 19    | pts  | good nights past 30d + max streak÷2    |
note: 
1. Current update: July 14
	1. cardio: 2.84+ 1.41+2.36+1.2+4.7+1.32+3.92+ (1+0.7+0.45) x 10 + (2.28 + 1.02 + 1.07 + 5.73)/4 = 41.775
	2. Rest: 16+6/2 
2. last manually check-in: May 11 = 68
## Storyteller inputs

| key               | value |
|-------------------|-------|
| speakings         | 7     |
| diaryLivestream   | 124   |
| specialLivestream | 1     |
note: speakings include TEM, BLF Academy, TCE (negotiation, storytelling, lawyering, AI network), Waki (Sidechat + onsite chat = 1)
## Side Quest — YouTube

| key         | value                              |
| ----------- | ---------------------------------- |
| number      | 124+                               |
| subtitle_en | Mandarin for now — Eng channel TBD |
| subtitle_zh | 日記直播 124+                          |

## PIF12 header

| key     | value                                                                                                         |
| ------- | ------------------------------------------------------------------------------------------------------------- |
| fillPct | 30                                                                                                            |
| hero_en | 12 years of commitment to a tribe of curious, grateful minds — Mainnet goes live June 21st, share your story! |
| hero_zh | 12 年的承諾，建立一個好奇博學者、樂於助人者的部落——6/21 上 mainnet，歡迎分享你的故事                                                           |

## PIF12 milestones

| key         | state | label_en        | label_zh | sub_en                 | sub_zh       | tooltip_en                                            | tooltip_zh               |
| ----------- | ----- | --------------- | -------- | ---------------------- | ------------ | ----------------------------------------------------- | ------------------------ |
| sketch      | done  | Sketch          | 構想       |                        |              | High-level design + landing page (EN/zh) shipped      | 設計概念與雙語 landing page 已上線 |
| onchain     | done  | Onchain         | 上鏈       | testnet → mainnet 6/21 | 測試 → 主網 6/21 | mainnet on 6/21                                       | 智能合約 6/21 上主網            |
| find-twelve | doing | Find Twelve     | 找到核心成員   | 10 of 12+              | 10 of 12+    | Find the first 12+ core members willing to hold SBTs  | 找到願意持有 SBT 的前 12+ 位核心成員  |
| year-end    |       | Year-End Gather | 年終聚會     | late 2026              | 2026 年底      | Year-end IRL gathering of the first twelve, late 2026 | 2026 年底十二人實體聚會           |
| y2-sbt      |       | Y2 SBT          | 第二年 SBT  | 2027                   | 2027         | Design and ship the Year-2 SBT (2027 cycle)           | 設計並推出 Y2 SBT（2027 週期）    |

## Meta

> `lastUpdate`: bump to today's date (YYYY-MM-DD) whenever you hand-edit numbers here (Wayfarer axes, Storyteller inputs, YouTube). The Three Roles "Last update" label shows the most recent of this date, the newest builder seed, and the newest published essay — so auto-driven changes surface even without a manual bump.
>
> `aiEssays`: how many *published* essays are AI-written (tagged `AI-generated`, counted as bilingual pairs). Subtracted from the Storyteller essay count so AI drafts don't inflate the score. Bump +1 each time you publish another AI-written essay pair.

| key        | value      |
| ---------- | ---------- |
| lastUpdate | 2026-07-14 |
| aiEssays   | 1          |
