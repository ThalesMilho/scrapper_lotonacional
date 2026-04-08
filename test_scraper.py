import sys
sys.path.insert(0, '/app')
import httpx, re
from bs4 import BeautifulSoup
from models.schemas import DrawEntry, DrawSession, SourceID

r = httpx.get("https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje", follow_redirects=True)
soup = BeautifulSoup(r.text, "lxml")
h = soup.find("h3", class_="h4")
label = " ".join(h.get_text().split())
table = h.find_next_sibling("table")
rows = table.find_all("tr")

# Try building one DrawEntry
cols = [td.get_text(strip=True) for td in rows[1].find_all("td")]
premio_num = re.sub(r"[^\d]", "", cols[0])
milhar = cols[1].zfill(4)
grupo_str = re.sub(r"[^\d]", "", cols[2])
print(f"Attempting DrawEntry: premio={premio_num} milhar={milhar} grupo={grupo_str} bicho={cols[3]}")
try:
    e = DrawEntry(premio=int(premio_num), milhar=milhar, centena=milhar[-3:], dezena=milhar[-2:], grupo=int(grupo_str), bicho=cols[3])
    print(f"DrawEntry OK: {e}")
except Exception as ex:
    print(f"DrawEntry FAILED: {ex}")

# Try building DrawSession
draw_date = re.search(r"(\d{2}/\d{2}/\d{4})", label).group(1)
draw_time = "09:00"
print(f"Attempting DrawSession: date={draw_date} time={draw_time}")
try:
    s = DrawSession(source_id=SourceID.BOA_SORTE, source_url="http://x.com", draw_date=draw_date, draw_time=draw_time, draw_label=label, state="GO", banca=None, entries=[])
    print(f"DrawSession OK: {s}")
except Exception as ex:
    print(f"DrawSession FAILED: {ex}")
