"""Post-analysis harvest for the staged CB27-48 single beam.

Run once the Civil NX API is responsive again.  Steps:
1. capture /db/stct (Construction Stage Analysis Control) if present --
   the schema we need to script future staged builds end-to-end;
2. list result load cases so the CS case naming is known;
3. pull the per-tendon loss table (TNDN_LOSS_FORCE) -> real f_pe;
4. pull per-stage PSC stresses and displacements;
5. pull the SlabCast-stage girder moment = M_dnc for the composite Mcr
   check (the last PENDING item in the Ch1 notebook).
Everything is dumped as JSON next to this script.
"""
import json
import sys

import pandas as pd

from civilpy.structural.midas import MidasCivil, parse_result_table

SP = "/tmp/claude-1000/-home-dane-projects-civilpy/0b2370e9-d203-4178-8385-d30c35d6b212/scratchpad"
m = MidasCivil()


def dump(name, obj):
    with open(f"{SP}/staged_{name}.json", "w") as f:
        json.dump(obj, f, indent=1, default=str)
    print(f"dumped staged_{name}.json")


# 1 -- analysis control schema (present only if the dialog was OK'd)
try:
    r = m.request("GET", "/db/stct", timeout=30, retries=0)
    print("stct:", json.dumps(r)[:400])
    dump("stct", r)
except Exception as e:
    print("stct GET failed:", str(e)[:120])

# 2 -- what result cases exist?  (harvest via a small table pull)
try:
    r = m.result_table("D", table_type="DISPLACEMENTG", timeout=120)
    rows = parse_result_table(r)
    df = pd.DataFrame(rows)
    print("displacement cases:", sorted(df.Load.unique()) if len(df) else "EMPTY")
    dump("disp", rows)
except Exception as e:
    print("no displacement results:", str(e)[:120])
    sys.exit("analysis results not present -- solve first")

# 3 -- per-tendon loss table (the reason we staged this model)
for tt in ("TNDN_LOSS_FORCE", "TNDN_LOSS_STRESS"):
    try:
        r = m.result_table("T", table_type=tt, timeout=180)
        rows = parse_result_table(r)
        print(tt, "->", len(rows), "rows")
        if rows:
            print("columns:", list(rows[0]))
            print("sample:", rows[0])
        dump(tt.lower(), rows)
    except Exception as e:
        print(tt, "failed:", str(e)[:120])

# 4 -- per-stage PSC stresses
try:
    r = m.result_table("S", table_type="BEAMSTRESSPSC", timeout=180)
    rows = parse_result_table(r)
    print("BEAMSTRESSPSC ->", len(rows), "rows; cases:",
          sorted({x["Load"] for x in rows}))
    dump("stress", rows)
except Exception as e:
    print("stress failed:", str(e)[:120])

# 5 -- girder moments per stage (SlabCast stage = M_dnc source)
try:
    r = m.result_table("F", table_type="BEAMFORCE", timeout=180)
    rows = parse_result_table(r)
    df = pd.DataFrame(rows)
    df["Moment-y"] = df["Moment-y"].astype(float)
    for case in sorted(df.Load.unique()):
        sub = df[df.Load == case]
        print(f"{case:30s} max |My| = {sub['Moment-y'].abs().max()/12:8.1f} kip-ft")
    dump("force", rows)
except Exception as e:
    print("force failed:", str(e)[:120])
print("HARVEST COMPLETE")
