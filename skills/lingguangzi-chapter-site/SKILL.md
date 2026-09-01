---
name: lingguangzi-chapter-site
description: Scan, validate, build, preview, and prepare publication of 靈魂療癒 chapter websites from a numbered local chapter folder. Use when the user says “N 章建立”, asks to refresh a chapter manifest, preview a chapter, or publish a confirmed chapter.
---

# 灵魂疗愈章节建站

把编号章节目录转换为可确认、可预览、可重复发布的响应式单页网站。

## 指令路由

- `N 章建立`：找到 `灵魂疗愈系列第 N 章`，执行 `scan_chapter.py ROOT --write`，依 inventory 候选角色产生 `chapter.json` 草稿并列出所有映射、排除与疑义供使用者一次确认。此时不得建站或发布。
- `N 章重新检查`／`更新第 N 章内容清单`：重新扫描；来源 digest 改变时把 confirmed 清单退回 draft，再提出差异。
- `预览第 N 章`：只在 `chapter.json` confirmed 且 lock 相符时执行 `build_chapter.py`；产生集中 QA 与本机预览。
- `确认发布第 N 章`：只有这句在当前回合出现，才允许 commit、push 与 GitHub Pages 验证。

## 必须遵守

1. 读取 [chapter schema](references/chapter-schema.md)，所有来源档案必须映射一次或明确排除；多首歌曲与精炼项目依 order 呈现。
2. Word、TXT 或可搜索 PDF 歌词以 `extract_lyrics.py` 转安全 HyperText；不得改写。扫描 PDF 回报 OCR，不可发布空歌词。
3. 读取 [内容与主视觉规则](references/content-and-visual-rules.md)。原封面不修改；AI 只另建 hero 与 1200×630 share 图，并通过最近六章差异检查。
4. 用 `build_chapter.py` 产生网站；保持 521 已确认的手机字级、初次载入顶端、三圆选项、Go Top、在线 PDF、单一媒体播放与 pagehide 停止。
5. 用 `qa_report.py` 集中回报。响应式与发布检查依 [QA 与发布边界](references/qa-and-release.md)。问题集中一次提出，不逐项来回询问。
6. Counter 使用 `site.config.json` 的 GoatCounter 公开站台代码；不得保存密码或 API key。

仓库中的 Skill 是唯一来源；个人 Skill 安装副本只在验证后同步。
