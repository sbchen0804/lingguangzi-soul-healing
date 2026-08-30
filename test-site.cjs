const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = __dirname;
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
for (const file of ['index.html', 'styles.css', 'script.js']) {
  assert.ok(fs.existsSync(path.join(root, file)), `${file} 應存在`);
}
const html = read('index.html');
const css = read('styles.css');
const js = read('script.js');

assert.ok(html.includes('<title>靈魂療癒系列｜第 521 章</title>'), '網站應有正確頁面標題');
assert.match(html, /id="entry-521"/, '首頁應提供三個閱讀入口');
assert.match(html, /id="original-reader"/, '原圖文應能在頁內閱讀');
assert.match(html, /id="song-521"/, '詩歌呈現應有專屬段落');
assert.match(html, /<details class="lyrics"/, '詩歌播放器下方應提供可展開的歌詞閱讀區');
assert.match(html, /<summary>閱讀歌詞<\/summary>/, '歌詞閱讀區應有清楚的開啟標示');
assert.match(html, /我要追著死亡地活著/, '歌詞閱讀區應收錄原始歌詞內容');
assert.match(css, /\.lyrics/, '歌詞閱讀區應有專屬閱讀樣式');
assert.match(html, /id="refined-521"/, '精煉篇應有專屬段落');
assert.match(html, /線上閱讀原圖文/, '原圖文應以線上閱讀為主');
assert.match(html, /assets\/chapter-521\/original-521-page-05\.png/, '原圖文應包含修正版第 5 頁');
assert.match(css, /\.page-stack\[aria-label\*="原圖文"\] figure\{aspect-ratio:850\/1100/, '原圖文頁面應預留正確圖片比例');
assert.match(css, /\.page-stack\[aria-label\*="精煉篇"\] figure\{aspect-ratio:1912\/1067/, '精煉篇頁面應預留正確圖片比例');
assert.equal((html.match(/assets\/chapter-521\/refined-521-page-\d{2}\.png/g) || []).length, 15, '精煉篇應包含 15 頁完整內容');
assert.match(html, /id="mini-player"/, '播放時應有常駐控制列');
assert.match(css, /background:\s*#fbfaf5 !important/, '頁首應固定淺色背景');
assert.match(js, /function setActiveEntry/, '入口選擇狀態應能隨段落更新');
assert.match(js, /event\.preventDefault\(\)/, '閱讀入口應攔截原生錨點跳轉');
assert.match(js, /function navigateToEntry/, '閱讀入口應在版面穩定後進行精確定位');
assert.match(js, /history\.pushState\(null, '', hash\)/, '閱讀入口應保留可分享的章節網址');
assert.match(js, /requestAnimationFrame/, '閱讀入口應在版面更新後再定位');
assert.match(js, /addEventListener\('pagehide'/, '離開頁面時音訊應停止');

console.log('PASS: standalone chapter 521 website has all primary reading flows and controls.');
