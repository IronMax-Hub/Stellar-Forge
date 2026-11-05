"""Check each plan reference against Crossref, then fetch abstracts (Semantic Scholar, arXiv fallback).

Usage: python3 -I refcheck.py <out.json>
Standard library only; writes JSON with metadata + abstracts, prints one line per reference.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

OUT = sys.argv[1]
UA = {"User-Agent": "StellarForge-refcheck/0.1"}

# key, Crossref query, expected (year, volume, first page / article id or None)
REFS = [
    ("Choi2016", "Choi 2016 MESA Isochrones and Stellar Tracks (MIST) I: Solar-scaled Models", (2016, "823", "102")),
    ("Dotter2016", "Dotter 2016 MESA Isochrones and Stellar Tracks (MIST) 0: Methods for the Construction of Stellar Isochrones", (2016, "222", "8")),
    ("Paxton2011", "Paxton 2011 Modules for Experiments in Stellar Astrophysics (MESA)", (2011, "192", "3")),
    ("Asplund2009", "Asplund 2009 The Chemical Composition of the Sun", (2009, "47", "481")),
    ("Prsa2016", "Prsa 2016 Nominal Values for Selected Solar and Planetary Quantities: IAU 2015 Resolution B3", (2016, "152", "41")),
    ("Cummings2018", "Cummings 2018 White Dwarf Initial-Final Mass Relation for Progenitor Stars from 0.85 to 7.5 solar masses", (2018, "866", "21")),
    ("Poelarends2008", "Poelarends 2008 The Supernova Channel of Super-AGB Stars", (2008, "675", "614")),
    ("Fryer2012", "Fryer 2012 Compact Remnant Mass Function: Dependence on the Explosion Mechanism and Metallicity", (2012, "749", "91")),
    ("HegerWoosley2002", "Heger Woosley 2002 The Nucleosynthetic Signature of Population III", (2002, "567", "532")),
    ("Heger2003", "Heger 2003 How Massive Single Stars End Their Life", (2003, "591", "288")),
    ("Belczynski2016", "Belczynski 2016 The effect of pair-instability mass loss on black-hole mergers", (2016, "594", "A97")),
    ("Farmer2019", "Farmer 2019 Mind the Gap: The Location of the Lower Edge of the Pair-instability Supernova Black Hole Mass Gap", (2019, "887", "53")),
    ("Bedard2020", "Bedard Bergeron Brassard Fontaine 2020 On the Spectral Evolution of Hot White Dwarf Stars I", (2020, "901", "93")),
    ("Hobbs2005", "Hobbs 2005 A statistical study of 233 pulsar proper motions", (2005, "360", "974")),
    ("Chandrasekhar1939", "Chandrasekhar An Introduction to the Study of Stellar Structure", (1939, None, None)),
    ("Kippenhahn2012", "Kippenhahn Weigert Weiss Stellar Structure and Evolution 2012", (2012, None, None)),
    ("IglesiasRogers1996", "Iglesias Rogers 1996 Updated OPAL Opacities", (1996, "464", "943")),
    ("Angulo1999", "Angulo 1999 A compilation of charged-particle induced thermonuclear reaction rates", (1999, "656", "3")),
    ("Hayashi1981", "Hayashi 1981 Structure of the Solar Nebula, Growth and Decay of Magnetic Fields and Effects of Magnetic and Turbulent Viscosities on the Nebula", (1981, "70", "35")),
    ("IdaLin2004a", "Ida Lin 2004 Toward a Deterministic Model of Planetary Formation I: A Desert in the Mass and Semimajor Axis Distributions of Extrasolar Planets", (2004, "604", "388")),
    ("IdaLin2004b", "Ida Lin 2004 Toward a Deterministic Model of Planetary Formation II: The Formation and Retention of Gas Giant Planets around Stars with a Range of Metallicities", (2004, "616", "567")),
    ("IdaLin2005", "Ida Lin 2005 Toward a Deterministic Model of Planetary Formation III: Mass Distribution of Short-Period Planets around Stars of Various Masses", (2005, "626", "1045")),
    ("IdaLin2008a", "Ida Lin 2008 Toward a Deterministic Model of Planetary Formation IV: Effects of Type I Migration", (2008, "673", "487")),
    ("IdaLin2008b", "Ida Lin 2008 Toward a Deterministic Model of Planetary Formation V: Accumulation Near the Ice Line and Super-Earths", (2008, "685", "584")),
    ("IdaLin2010", "Ida Lin 2010 Toward a Deterministic Model of Planetary Formation VI: Dynamical Interaction and Coagulation of Multiple Rocky Embryos and Super-Earth Systems around Solar-type Stars", (2010, "719", "810")),
    ("KokuboIda1998", "Kokubo Ida 1998 Oligarchic Growth of Protoplanets", (1998, "131", "171")),
    ("KokuboIda2002", "Kokubo Ida 2002 Formation of Protoplanet Systems and Diversity of Planetary Systems", (2002, "581", "666")),
    ("Ikoma2000", "Ikoma Nakazawa Emori 2000 Formation of Giant Planets: Dependences on Core Accretion Rate and Grain Opacity", (2000, "537", "1013")),
    ("Andrews2013", "Andrews 2013 The Mass Dependence between Protoplanetary Disks and their Stellar Hosts", (2013, "771", "129")),
    ("Mamajek2009", "Mamajek 2009 Initial Conditions of Planet Formation: Lifetimes of Primordial Disks", (2009, "1158", "3")),
    ("ChenKipping2017", "Chen Kipping 2017 Probabilistic Forecasting of the Masses and Radii of Other Worlds", (2017, "834", "17")),
    ("LambrechtsJohansen2012", "Lambrechts Johansen 2012 Rapid growth of gas-giant cores by pebble accretion", (2012, "544", "A32")),
    ("Emsenhuber2021", "Emsenhuber 2021 The New Generation Planetary Population Synthesis (NGPPS) I. Bern global model of planet formation and evolution", (2021, "656", "A69")),
    ("FischerValenti2005", "Fischer Valenti 2005 The Planet-Metallicity Correlation", (2005, "622", "1102")),
    ("Johnson2010", "Johnson 2010 Giant Planet Occurrence in the Stellar Mass-Metallicity Plane", (2010, "122", "905")),
    ("Cumming2008", "Cumming 2008 The Keck Planet Search: Detectability and the Minimum Mass and Orbital Period Distribution of Extrasolar Planets", (2008, "120", "531")),
    ("Buchhave2012", "Buchhave 2012 An abundance of small exoplanets around stars with a wide range of metallicities", (2012, "486", "375")),
    ("Petigura2018", "Petigura 2018 The California-Kepler Survey IV: Metal-rich Stars Host a Greater Diversity of Planets", (2018, "155", "89")),
    ("Kopparapu2013", "Kopparapu 2013 Habitable Zones around Main-sequence Stars: New Estimates", (2013, "765", "131")),
    ("Kopparapu2014", "Kopparapu 2014 Habitable Zones around Main-sequence Stars: Dependence on Planetary Mass", (2014, "787", "L29")),
    ("Veras2011", "Veras 2011 The great escape: how exoplanets and smaller bodies desert dying stars", (2011, "417", "2104")),
    ("Zahn1977", "Zahn 1977 Tidal friction in close binary stars", (1977, "57", "383")),
    ("VerbuntPhinney1995", "Verbunt Phinney 1995 Tidal circularization and the eccentricity of binaries containing giant stars", (1995, "296", "709")),
    ("VillaverLivio2009", "Villaver Livio 2009 The Orbital Evolution of Gas Giant Planets around Giant Stars", (2009, "705", "L81")),
    ("MustillVillaver2012", "Mustill Villaver 2012 Foretellings of Ragnarok: World-engulfing Asymptotic Giants and the Inheritance of White Dwarfs", (2012, "761", "121")),
    ("SchroderSmith2008", "Schroder Connon Smith 2008 Distant future of the Sun and Earth revisited", (2008, "386", "155")),
    ("Hills1983", "Hills 1983 The effects of sudden mass loss and a random kick velocity produced in a supernova explosion on the dynamics of a binary star of arbitrary orbital eccentricity", (1983, "267", "322")),
    ("WolszczanFrail1992", "Wolszczan Frail 1992 A planetary system around the millisecond pulsar PSR1257+12", (1992, "355", "145")),
    ("OwenWu2017", "Owen Wu 2017 The Evaporation Valley in the Kepler Planets", (2017, "847", "29")),
    ("Fulton2017", "Fulton 2017 The California-Kepler Survey III: A Gap in the Radius Distribution of Small Planets", (2017, "154", "109")),
    ("Kroupa2001", "Kroupa 2001 On the variation of the initial mass function", (2001, "322", "231")),
    ("HolmanWiegert1999", "Holman Wiegert 1999 Long-Term Stability of Planets in Binary Systems", (1999, "117", "621")),
    ("Wright2011", "Wright 2011 The Stellar-activity-Rotation Relationship and the Evolution of Stellar Dynamos", (2011, "743", "48")),
    ("Ribas2005", "Ribas 2005 Evolution of the Solar Activity over Time and Effects on Planetary Atmospheres I: High-Energy Irradiances (1-1700 A)", (2005, "622", "680")),
    ("ZahnleCatling2017", "Zahnle Catling 2017 The Cosmic Shoreline: The Evidence that Escape Determines which Planets Have Atmospheres", (2017, "843", "122")),
    ("Sana2012", "Sana 2012 Binary Interaction Dominates the Evolution of Massive Stars", (2012, "337", "444")),
    # extra sources used to check specific numbers
    ("OzelFreire2016", "Ozel Freire 2016 Masses, Radii, and the Equation of State of Neutron Stars", (2016, "54", "401")),
    ("Riley2019", "Riley 2019 A NICER View of PSR J0030+0451: Millisecond Pulsar Parameter Estimation", (2019, "887", "L21")),
    ("Miller2019", "Miller 2019 PSR J0030+0451 Mass and Radius from NICER Data and Implications for the Properties of Neutron Star Matter", (2019, "887", "L24")),
    ("Gough1981", "Gough 1981 Solar Interior Structure and Luminosity Variations", (1981, "74", "21")),
    ("Woosley2017", "Woosley 2017 Pulsational Pair-instability Supernovae", (2017, "836", "244")),
]


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(4 * (i + 1))


def year_of(it):
    for k in ("published-print", "published-online", "issued"):
        parts = (it.get(k) or {}).get("date-parts") or [[None]]
        if parts[0] and parts[0][0]:
            return parts[0][0]
    return None


results = {}
for key, q, exp in REFS:
    txt = get("https://api.crossref.org/works?rows=5&query.bibliographic=" + urllib.parse.quote(q))
    rec = {"query": q, "expected": exp}
    if txt:
        items = json.loads(txt)["message"]["items"]
        same_year = [it for it in items if year_of(it) == exp[0]]
        it = (same_year or items or [None])[0]
        if it:
            rec.update(
                doi=it.get("DOI"),
                title=(it.get("title") or [""])[0],
                journal=(it.get("container-title") or [""])[0],
                volume=it.get("volume"),
                page=it.get("page") or it.get("article-number"),
                year=year_of(it),
                first_author=((it.get("author") or [{}])[0]).get("family"),
            )
    results[key] = rec
    time.sleep(0.3)

for key, rec in results.items():
    if not rec.get("doi"):
        continue
    txt = get("https://api.semanticscholar.org/graph/v1/paper/DOI:" + urllib.parse.quote(rec["doi"]) + "?fields=abstract,externalIds")
    if txt:
        d = json.loads(txt)
        rec["abstract"] = d.get("abstract")
        rec["arxiv"] = (d.get("externalIds") or {}).get("ArXiv")
    time.sleep(1.2)

for key, rec in results.items():
    if not rec.get("abstract") and rec.get("arxiv"):
        txt = get("http://export.arxiv.org/api/query?id_list=" + rec["arxiv"])
        m = re.search(r"<entry>.*?<summary>(.*?)</summary>", txt or "", re.S)
        if m:
            rec["abstract"] = " ".join(m.group(1).split())
        time.sleep(3)

with open(OUT, "w") as f:
    json.dump(results, f, indent=1)

for key, rec in results.items():
    y, v, p = rec["expected"]
    ok = rec.get("year") == y and (v is None or str(rec.get("volume")) == v) and (p is None or str(rec.get("page") or "").split("-")[0] == p)
    print(
        f"{'OK ' if ok else 'CHK'} {key}: {rec.get('first_author')} {rec.get('year')} | {str(rec.get('journal'))[:28]} {rec.get('volume')} {rec.get('page')} "
        f"| doi:{rec.get('doi')} | {str(rec.get('title'))[:80]} | abs:{'y' if rec.get('abstract') else 'n'} arxiv:{rec.get('arxiv')}"
    )
