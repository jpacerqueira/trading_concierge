#!/usr/bin/env python3
"""
Generates a Murex 2.0 MX Trade Blotter CSV with 500 synthetic trades
following the exact same schema and variable types as the source file.
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)

# ---- Schema header (line 1, exact) ----
HEADER = [
    "VirtualSelected", "Source", "Package nb", "Contract nb", "Version",
    "Trade nb", "Last event", "Status", "BuySell", "Typology", "Instrument",
    "Amount", "DealYield", "DealPrice", "Face cur", "Maturity",
    "Counterparty", "Portfolio", "User"
]

# ---- Profiled domains (taken from the source file) ----
SOURCES = ["mx", "mx", "mx", "mx", "mx", "mx", "mx", "mx",
           "REUTERS DEALING", "BLOOMBERG FXGO", "REUTERS", "FXALL"]

LAST_EVENT_OPTIONS = [""] * 50 + ["Cancel"]  # rarely populated
STATUS_OPTIONS     = ["Ins"] * 50 + ["Cncl"]  # rarely cancelled

TYPOLOGIES = ["Outright", "Spot"]

# FX pairs observed in source + base currency mapping
INSTRUMENTS = {
    "EUR/CHF": {"base": "EUR", "spot": 0.9550, "vol": 0.015},
    "EUR/USD": {"base": "EUR", "spot": 1.0951, "vol": 0.020},
    "USD/AED": {"base": "USD", "spot": 3.67300, "vol": 0.0005},
    "USD/CAD": {"base": "USD", "spot": 1.3309,  "vol": 0.015},
    "EUR/CAD": {"base": "EUR", "spot": 1.4580,  "vol": 0.018},
    "USD/ZAR": {"base": "USD", "spot": 18.6055, "vol": 0.25},
    "EUR/GBP": {"base": "EUR", "spot": 0.8599,  "vol": 0.010},
    "USD/JPY": {"base": "USD", "spot": 144.23,  "vol": 1.50},
    "USD/CHF": {"base": "USD", "spot": 0.848,   "vol": 0.012},
    "GBP/USD": {"base": "GBP", "spot": 1.27485, "vol": 0.018},
}
INSTRUMENT_LIST = list(INSTRUMENTS.keys())

COUNTERPARTIES = [
    "CITIBANK N A", "BARCLAYS BANK", "ABBEY NATIONAL PLC",
    "ABN AMRO AMS", "ABSA ASSET MANAGEMENT", "TESCO PLC",
    "BOUYGUES", "COMPANY B", "COMPANY C",
    # internal books observed as counterparty column in the source too:
    "FWD_AED_LN", "FWD_EUR_LN", "FWD_CAD_LN", "FWD_GBP_LN",
    "FWD_CHF_LN", "FWD_JPY_LN",
    "SPT_EUR_LN", "SPT_CAD_LN", "SPT_GBP_LN", "SPT_CHF_LN", "SPT_JPY_LN",
]

PORTFOLIOS = [
    "FXMM_SALES1", "FXMM_SALES3", "FXMM_TRADER1", "FXMM_TRADER2",
    "FXMM_TRADER3", "FWD_AED_LN", "FWD_EUR_LN", "FWX_EURCHF_LN",
    "A-OTC", "HQ_TT_FXCSWP01",
]

USERS = ["MYTRADERFO"]

AMOUNT_BUCKETS = [
    (-12, 12), (-1000, 1000), (-100000, 100000),
    (-1_000_000, 1_000_000), (-10_000_000, 10_000_000),
    (-100_000_000, 100_000_000),
]

# Maturity date formats observed in the file
DATE_FORMATS = ["%d-%b-%y", "%d %b %Y", "%d-%b-%Y"]
# special quirk in source: "11-Sept-24" (4-char month abbreviation)

def gen_maturity(base_date: datetime) -> str:
    offset_days = random.choice([0, 1, 7, 30, 60, 90, 120, 180, 270, 365, 540])
    d = base_date + timedelta(days=offset_days)
    fmt = random.choice(DATE_FORMATS)
    out = d.strftime(fmt)
    # Emulate the "Sept" quirk occasionally
    if d.month == 9 and random.random() < 0.3:
        out = out.replace("Sep", "Sept")
    return out


def gen_amount() -> int | float:
    low, high = random.choice(AMOUNT_BUCKETS)
    a = random.randint(low, high)
    # occasional decimal (as seen for USD/CAD rows like -1562040.2)
    if random.random() < 0.08:
        a = round(a + random.random(), 2)
    # avoid zero
    if a == 0:
        a = random.choice([-1, 1]) * random.randint(1, 1000)
    return a


def gen_deal_price(pair: str, typology: str) -> float:
    cfg = INSTRUMENTS[pair]
    spot = cfg["spot"]
    vol  = cfg["vol"]
    # small drift for forwards
    drift = 0 if typology == "Spot" else random.uniform(-vol, vol) * 3
    price = spot + random.uniform(-vol, vol) + drift
    # precision like in source file (4-8 dp)
    dp = random.choice([3, 4, 5, 6, 7, 8])
    return round(price, dp)


def gen_face_cur(pair: str) -> str:
    # roughly aligned with source: base of pair, but occasionally the quote
    base, quote = pair.split("/")
    return base if random.random() < 0.85 else quote


BASE_DATE = datetime(2024, 1, 11)

def generate_rows(n: int):
    rows = []
    trade_nb   = 593900   # continue numbering after source
    contract   = 595800
    package    = 595800
    # ~70% of rows share a package (mini-deals of 2–4 contracts), like source
    i = 0
    while i < n:
        group_size = random.choices([1, 2, 3, 4], weights=[25, 30, 30, 15])[0]
        pkg = package if group_size > 1 else 0
        package += group_size + random.randint(1, 5)

        # pick a counterparty for the whole package (source shows this pattern)
        cp_final      = random.choice(COUNTERPARTIES)
        portfolio     = random.choice(PORTFOLIOS)
        pair          = random.choice(INSTRUMENT_LIST)

        for g in range(group_size):
            if i >= n:
                break
            contract += 1
            trade_nb += 1
            typology = random.choice(TYPOLOGIES)
            amount   = gen_amount()
            price    = gen_deal_price(pair, typology)
            face_cur = gen_face_cur(pair)
            maturity = gen_maturity(BASE_DATE if typology == "Spot" else BASE_DATE)
            status   = random.choice(STATUS_OPTIONS)
            last_ev  = "Cancel" if status == "Cncl" else ""

            rows.append([
                "N",
                random.choice(SOURCES),
                pkg,
                contract,
                random.choices([1, 2], weights=[95, 5])[0],
                trade_nb,
                last_ev,
                status,
                "",                                # BuySell (empty in source)
                typology,
                pair,
                amount,
                0,                                 # DealYield (always 0 in source)
                price,
                face_cur,
                maturity,
                cp_final,
                portfolio,
                random.choice(USERS),
            ])
            i += 1
    return rows


def main():
    out_path = "/sessions/awesome-quirky-archimedes/mnt/outputs/MX-TradeBlotter-generated-500.csv"
    rows = generate_rows(500)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";", quoting=csv.QUOTE_MINIMAL,
                       lineterminator="\n")
        w.writerow(HEADER)
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
