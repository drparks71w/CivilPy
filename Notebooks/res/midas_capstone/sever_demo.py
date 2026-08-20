"""Restructure transverse members (keys vs diaphragms), then run the
severed-tendon comparison: baseline vs 4 severed strands on girder 3."""
import base64
import pandas as pd

from civilpy.structural.midas import MidasCivil, parse_result_table

m = MidasCivil()
SP = "/tmp/claude-1000/-home-dane-projects-civilpy/0b2370e9-d203-4178-8385-d30c35d6b212/scratchpad"
NG, NS, DX, DY = 6, 15, 60.0, 48.0


def nid(g, s):
    return g * 100 + s


def rect(name, h, b):
    return {"SECTTYPE": "DBUSER", "SECT_NAME": name,
            "SECT_BEFORE": {"SHAPE": "SB", "DATATYPE": 2,
                            "SECT_I": {"vSIZE": [h, b]},
                            "OFFSET_PT": "CC", "OFFSET_CENTER": 0,
                            "USER_OFFSET_REF": 0, "HORZ_OFFSET_OPT": 0,
                            "USERDEF_OFFSET_YI": 0.0, "VERT_OFFSET_OPT": 0,
                            "USERDEF_OFFSET_ZI": 0.0,
                            "USE_SHEAR_DEFORM": True,
                            "USE_WARPING_EFFECT": False}}


# ── 1. sections: slim key strips + true diaphragms ───────────────────────
m.request("PUT", "/db/SECT", {"Assign": {
    "2": rect("KeyStrip", 20.0, 4.0),
    "3": rect("Diaphragm", 27.0, 12.0),
}})
# diaphragms at the third-point nodes (stations 5 and 11: x = 240, 600),
# full-depth, moment-connected (no releases)
diaph = {}
for g in range(NG - 1):
    for s in (5, 11):
        eid = 2000 + g * 20 + s
        diaph[str(eid)] = {"TYPE": "BEAM", "MATL": 1, "SECT": 3,
                           "NODE": [nid(g, s), nid(g + 1, s)], "ANGLE": 0}
m.request("PUT", "/db/ELEM", {"Assign": diaph})
print("sections + diaphragms updated")

# ── 2. baseline analysis and results ─────────────────────────────────────
m.request("POST", "/doc/ANAL", {"Argument": {}}, timeout=550, retries=0)


def girder3_state(tag):
    disp = m.result_table("D", table_type="DISPLACEMENTG",
                          load_case_names=["PS(ST)", "DC(ST)"], timeout=300)
    dd = pd.DataFrame(parse_result_table(disp))
    dd["DZ"] = dd["DZ"].astype(float)
    g3 = dd[dd.Node.astype(int).between(201, 215)]
    net = g3.groupby("Node", sort=False)["DZ"].sum()  # DC + PS superposed
    mid = float(net.loc["208"]) if "208" in net.index else float(net.iloc[7])
    st = m.result_table("S", table_type="BEAMSTRESSPSC",
                        load_case_names=["PS(ST)", "DC(ST)"], timeout=300)
    ss = pd.DataFrame(parse_result_table(st))
    row = ss[(ss.Elem == "207") & (ss.Part == "3/4")
             & (ss.SectionPosition.isin(["Pos-3", "Pos-4"]))]
    bot = row["Sig-xx(Summation)"].astype(float).sum() / max(len(row) // 2, 1)
    # sum over the two cases per position -> average the two bottom corners
    bots = row.groupby("SectionPosition")["Sig-xx(Summation)"].apply(
        lambda s: s.astype(float).sum())
    bot = bots.mean()
    print(f"[{tag}] girder-3 midspan net DZ = {mid:.3f} in, "
          f"bottom fiber (DC+PS) = {bot:.3f} ksi")
    return mid, bot


base_dz, base_bot = girder3_state("baseline")

# ── 3. sever 4 outermost bottom-row strands on girder 3 ──────────────────
# girder 3 tendons are ids 65..96; bottom row = 65..80 sorted by y
# ascending, so outermost four are 65, 66 (y=-20,-18) and 79, 80 (+18,+20)
severed = [65, 66, 79, 80]
for tid in severed:
    m.request("DELETE", f"/db/TDPL/{tid}")
    m.request("DELETE", f"/db/TDNA/{tid}")
print("severed tendons:", severed)

m.request("POST", "/doc/ANAL", {"Argument": {}}, timeout=550, retries=0)
sev_dz, sev_bot = girder3_state("severed")

print(f"\ndelta: DZ {sev_dz - base_dz:+.3f} in, "
      f"bottom fiber {sev_bot - base_bot:+.3f} ksi "
      f"({(sev_bot - base_bot):.3f} ksi of precompression lost)")

# ── 4. capture the severed deformed shape from the app ───────────────────
graphic = {
    "CURRENT_MODE": "DeformedShape",
    "LOAD_CASE_COMB": {"TYPE": "ST", "NAME": "PS", "MINMAX": "Max",
                       "STEP_INDEX": 2, "TH_OPTION": "Displacement"},
    "COMPONENTS": {"COMP": "DZ", "OPT_LOCAL_CHECK": False},
    "TYPE_OF_DISPLAY": {
        "DEFORM": {"OPT_CHECK": True, "SCALE_FACTOR": 1.0,
                   "REL_DISP": False, "REAL_DISP": False,
                   "REAL_DEFORM": False},
        "VALUES": {"OPT_CHECK": False, "VALUE_EXP": False,
                   "DECIMAL_PT": 1, "SET_ORIENT": 0},
        "LEGEND": {"OPT_CHECK": True, "POSITION": "right",
                   "VALUE_EXP": False, "DECIMAL_PT": 2},
        "MIRRORED": {"OPT_CHECK": False},
        "UNDEFORMED": {"OPT_CHECK": True},
        "OPT_CUR_STEP_DISPLACEMENT": True,
        "OPT_STAGE_STEP_REAL_DISPLACEMENT": True,
        "OPT_INCLUDING_CAMBER_DISPLACEMENT": True,
    },
}
r = m.request("POST", "/view/CAPTURE", {"Argument": {
    "SET_MODE": "post", "HEIGHT": 720, "WIDTH": 1280,
    "ANGLE": {"HORIZONTAL": 30, "VERTICAL": 20},
    "RESULT_GRAPHIC": graphic}}, timeout=200)
open(f"{SP}/midas_deform_severed.png", "wb").write(
    base64.b64decode(r["base64String"]))
print("captured severed deformed shape")
