"""Print the abstract sentences that bear on each plan claim.

Usage: python3 -I claims_check.py <refs.json>
"""
import json
import re
import sys

refs = json.load(open(sys.argv[1]))

CLAIMS = {
    "Choi2016": [r"0\.1", r"300", r"\[Z/H\]|\[Fe/H\]|metallicit", r"rotat", r"solar"],
    "Dotter2016": [r"equivalent evolutionary|EEP"],
    "Prsa2016": [r"5772|effective temperature"],
    "Cummings2018": [r"MIST|PARSEC", r"scatter|dispersion", r"initial"],
    "Poelarends2008": [r"electron.capture|ECSN|range|M_?\\?odot|Msun|solar mass"],
    "Fryer2012": [r"rapid|delayed", r"gap", r"neutron star"],
    "HegerWoosley2002": [r"64|133|140|260", r"pair"],
    "Heger2003": [r"metallicit", r"black hole"],
    "Belczynski2016": [r"40|45|65|pulsation"],
    "Farmer2019": [r"45|gap|robust|metallicit"],
    "Woosley2017": [r"helium core|30|64|pulsation"],
    "Bedard2020": [r"evolutionary|cooling|sequence"],
    "Hobbs2005": [r"265|Maxwellian"],
    "IdaLin2004a": [r"desert|deterministic|10.?100"],
    "IdaLin2004b": [r"metallicit|\[Fe/H\]"],
    "IdaLin2005": [r"stellar mass|M_\*|0\.2|1\.5|M dwarf"],
    "IdaLin2008a": [r"type I|C_1|reduc|efficien"],
    "IdaLin2010": [r"embryo|giant impact|super-Earth"],
    "Andrews2013": [r"linear|scal|M_\*|stellar mass"],
    "Mamajek2009": [r"Myr|e-folding|lifetime"],
    "ChenKipping2017": [r"2\.0|0\.41|transition"],
    "Johnson2010": [r"1\.0|1\.2|M_\*|\[Fe/H\]|stellar mass"],
    "Cumming2008": [r"10\.5|0\.3|2000"],
    "Petigura2018": [r"metal|sub-Neptune|super-Earth"],
    "Kopparapu2013": [r"0\.99|0\.97|1\.70|1\.67|2600|7200|moist|runaway"],
    "Kopparapu2014": [r"mass|inner"],
    "Veras2011": [r"adiabatic"],
    "VillaverLivio2009": [r"tid|engulf|RGB|red giant"],
    "MustillVillaver2012": [r"AGB|engulf|AU"],
    "SchroderSmith2008": [r"256|1\.2|AU|Earth|engulf|mass"],
    "OwenWu2017": [r"valley|gap|R_\\?oplus|Earth radii"],
    "Fulton2017": [r"gap|1\.5|2\.0|Earth radii"],
    "Kroupa2001": [r"1\.3|2\.3|0\.08|0\.5"],
    "HolmanWiegert1999": [r"critical|stab"],
    "Wright2011": [r"3\.13|saturat|0\.13"],
    "ZahnleCatling2017": [r"shoreline|escape velocity|v_\{?esc|\^4|fourth"],
    "Sana2012": [r"70|%|interact"],
    "OzelFreire2016": [r"1\.1|2\.0|km|mass"],
    "Riley2019": [r"km|radius"],
    "Miller2019": [r"km|radius"],
    "LambrechtsJohansen2012".replace("J", "J"): [r"pebble"],
    "Emsenhuber2021": [r"population|Bern"],
}

for key, pats in CLAIMS.items():
    abstract = (refs.get(key) or {}).get("abstract")
    if not abstract:
        print(f"## {key}: no abstract retrieved")
        continue
    sentences = re.split(r"(?<=[.!?])\s+", abstract)
    hits = [s for s in sentences if any(re.search(p, s, re.I) for p in pats)]
    print(f"## {key}")
    for s in hits[:6]:
        print("   -", s[:420])
