"""Print short windows around regex matches in downloaded paper texts.

Usage: python3 -I text_grep.py <papers_dir>
"""
import os
import re
import sys

D = sys.argv[1]
CHECKS = {
    "astro-ph_0312144.txt": [r"2400", r"4\.2", r"η\s*ice|eta_?ice|ηice", r"τ\s*dep|τdep", r"10\s*6\s*.{0,8}10\s*7|10\^6|106\s*[–-]\s*107", r"log.?normal|Gaussian distribution", r"Mc,?\s*hydro|critical core"],
    "astro-ph_0408019.txt": [r"10\s*\[Fe/H\]|10\[Fe/H\]|fd\s*=\s*fg|f\s*d\s*=\s*f\s*g"],
    "astro-ph_0502566.txt": [r"2\.7", r"0\.2\s*M|M∗\s*=\s*0\.2|range of M", r"\(M\s*∗\s*/\s*M⊙\)\s*2|M∗\s*/M⊙\s*\)2"],
    "0802.1114.txt": [r"C\s*1\s*=|C1\s*=|C_1", r"0\.01|0\.03|0\.1\b"],
    "1110.1726.txt": [r"maximum neutron star mass|maximum NS mass|NS mass", r"2\.5\s*M|3\.0?\s*M⊙", r"rapid", r"delayed"],
    "1607.03116.txt": [r"45\s*[–-]\s*65|40\.5", r"helium core"],
    "1301.6674.txt": [r"0\.97", r"runaway greenhouse", r"1\.0146|1\.0385|1\.0512|1\.107", r"0\.99\s*AU"],
    "1604.08592.txt": [r"0\.1\s*(?:≤|<|to)|≤\s*300|300\s*M", r"−4\.0|-4\.0|−4\.00", r"v/v\s*crit|vvcrit|Ω/Ω\s*crit", r"0\.249", r"0\.2703|0\.0142", r"5772|calibrat"],
}

for fname, pats in CHECKS.items():
    path = os.path.join(D, fname)
    if not os.path.exists(path):
        print(f"## {fname}: missing")
        continue
    text = " ".join(open(path, errors="replace").read().split())
    print(f"## {fname}")
    for p in pats:
        hits = [m.start() for m in re.finditer(p, text, re.I)][:3]
        for h in hits:
            print(f"   [{p[:18]}] …{text[max(0, h - 160): h + 200]}…")
