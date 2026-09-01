from pathlib import Path

from PIL import Image
from reportlab.pdfgen.canvas import Canvas


ROOT = Path(__file__).parent / "fixtures"
CHAPTER = ROOT / "chapter-999"
(CHAPTER / "原圖文").mkdir(parents=True, exist_ok=True)
(CHAPTER / "詩歌創作").mkdir(parents=True, exist_ok=True)

Image.new("RGB", (32, 32), "#dbe8df").save(CHAPTER / "原圖文/cover.png")
canvas = Canvas(str(CHAPTER / "原圖文/original.pdf"))
canvas.drawString(72, 720, "chapter 999 original")
canvas.save()
(CHAPTER / "詩歌創作/song.mp3").write_bytes(b"ID3")
(CHAPTER / "詩歌創作/lyrics.txt").write_text("主歌一\n今天\n\n副歌\n好好活著", encoding="utf-8")

scanned = Image.new("RGB", (640, 800), "white")
scanned.save(ROOT / "scanned-one-page.pdf", "PDF", resolution=144)
