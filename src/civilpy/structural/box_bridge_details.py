"""Synthetic box-beam coordination models, in feet (X station, Y transverse).

These examples expose physical envelopes and unresolved clashes. They are not
fabrication models or independently designed foundations. See the generated
limitations and docs/Box_Bridge_Details.md for what is and is not checked.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math

from civilpy.structural.steel import Rebar
from civilpy.structural.bridge_layout import girder_section
from civilpy.structural.odot import BEARING_PADS, box_beam_design, diaphragm_stations_ft
from civilpy.structural.odot.approach_slab import ApproachSlabInput, layout_approach_slab
from civilpy.structural.odot.sleeper_slab import SleeperSlabInput, layout_sleeper_slab
from civilpy.structural.rhino_bim import BridgeEmit, EmitObject, i_profile_wh
from civilpy.structural.rhino_box_bim import BoxBridgeInput, box_beam_bridge_emit, _rect_prism
from civilpy.structural.detail_geometry import swept_solid


@dataclass(frozen=True)
class BoxDetailInput:
    abutment: str = "integral"
    grade_pct: float = 1.0
    crossfall_pct: float = 2.0
    crown: bool = True
    profile_rise_in: float = 1.0
    approach_length_ft: float = 25.0
    foundation: str = "auto"
    railing: str = "DBR-3"
    terminal: str = "buried"
    scenario_id: str = ""


LIMITATIONS = (
    "Synthetic 60 ft CB27-48, eight-beam, zero-skew waterway example; no site data.",
    "Foundation sizes, pile lengths and substructure bar spacing are coordination assumptions, not load/geotechnical designs.",
    "Beam camber is zero in these examples; construction camber and bearing reaction/movement checks remain required.",
    "Box section keyways, void fillets, strand individualization and reinforcement development are not fully modeled.",
    "Rail and termination assemblies are dimensional coordination envelopes; corrugation radii, slots, all bolts and fabrication tolerances are not fully modeled.",
    "DBR-3 examples represent restricted non-NHS, non-ODOT-maintained waterway applications; Type A is an existing local-road comparison, not a general new-road recommendation.",
    "Type T examples assume one-way +X traffic and placement outside opposing-traffic clear zones; upstream ends use buried terminals.",
    "AS-1-15 catalog omits A-bar bends and D801 terminal hooks; clashes near those missing bends are not certified clear.",
    "Clash checks cover selected circular steel envelopes, not all concrete, joint hardware or minimum code spacing.",
)


def post_stations(span, tie_stations):
    """Shortest chain of posts <=8 ft apart, >=18 in from transverse ties."""
    candidates = [i/4 for i in range(10, int((span-2.5)*4)+1)
                  if all(abs(i/4-t) >= 1.5-1e-9 for t in tie_stations)]
    start, end = candidates[0], candidates[-1]
    paths = {start: (start,)}
    for x in candidates[1:]:
        previous = [p for p in paths if 0 < x-p <= 8.]
        if previous:
            p = min(previous, key=lambda p: (len(paths[p]), -p))
            paths[x] = paths[p]+(x,)
    if end not in paths:
        raise ValueError("No TST-2 post layout meeting spacing and tie-rod clearance")
    return paths[end]


def detailed_box_bridge_emit(inp=BoxDetailInput()):
    if inp.abutment not in ("integral", "semi-integral", "seat"):
        raise ValueError("abutment must be integral, semi-integral or seat")
    foundation = ("piles" if inp.abutment == "integral" else "spread") if inp.foundation == "auto" else inp.foundation
    if foundation not in ("piles", "spread", "shafts"):
        raise ValueError("foundation must be auto, piles, spread or shafts")
    if inp.abutment == "integral" and foundation != "piles":
        raise ValueError("This integral detail requires flexible piles; use semi-integral/seat for spread or shafts")
    if inp.railing not in ("DBR-3", "TST-2"):
        raise ValueError("railing must be DBR-3 or TST-2")
    if inp.terminal not in ("buried", "type_a", "trailing_t"):
        raise ValueError("terminal must be buried, type_a or trailing_t")
    if not all(math.isfinite(x) for x in (inp.grade_pct, inp.crossfall_pct, inp.profile_rise_in)):
        raise ValueError("Road geometry must be finite")
    if not (0 < inp.crossfall_pct <= 2 and abs(inp.grade_pct) <= 1):
        raise ValueError("Example bearing rotation envelope requires grade <=1%, crossfall >0..2%")
    if not 0 <= inp.profile_rise_in <= 2:
        raise ValueError("Example topping/railing envelope requires profile rise 0..2 in")
    span, width, depth = 60., 32., 27/12
    base = box_beam_bridge_emit(BoxBridgeInput("CB27-48", span, 8, fc_psi=7000))
    pad = BEARING_PADS[box_beam_design("CB27-48", 60).bearing_type]
    pad_t = pad.total_thickness/12
    objects = []
    prefix = inp.scenario_id or inp.abutment

    def cross(y):
        return inp.crossfall_pct/100*(min(y, width-y) if inp.crown else -y)

    def beam_z(x, y):
        return inp.grade_pct/100*x+cross(y)

    def profile(x):
        # Tangent continuation into each approach; parabolic crest over span.
        h = inp.profile_rise_in/12
        if x < 0:
            return 4*h*x/span
        if x > span:
            return -4*h*(x-span)/span
        return 4*h*x*(span-x)/span**2

    def road(x, y):
        return depth+7/12+beam_z(x, y)+profile(x)

    def tag(kind, ident, source="", **extra):
        return {"bim.type": kind, "bim.id": f"{prefix}-{ident}",
                "bim.scd": source, **{k: str(v) for k, v in extra.items()}}

    def add(o):
        objects.append(replace(o, layer=f"{prefix}::{o.layer}"))

    def solid(ident, kind, x0, x1, y0, y1, z0, z1, source="", surface=beam_z):
        # Split at crown so every profile/extrusion is planar.
        cuts = [y0]+([16.] if inp.crown and y0 < 16 < y1 else [])+[y1]
        for j, (a, b) in enumerate(zip(cuts, cuts[1:])):
            o = _rect_prism(kind, x0, x1, a, b, z0, z1, tag(kind, f"{ident}-{j}", source))
            add(replace(o, points=tuple((x, y, z+surface(x, y)) for x, y, z in o.points)))

    def bar(ident, group, points, size=5, source="", diameter=None):
        is_rebar = diameter is None
        diameter = float(Rebar(size).diameter.magnitude) if is_rebar else diameter
        tags = tag("rebar" if is_rebar else "anchor", ident, source,
                   **{"clash.group": group, "rebar.dia_in": diameter, "rebar.size": size})
        # One logical centerline for collision and schedule; cylindrical segments
        # for solid review. Only centerlines have clash.group to prevent duplicates.
        add(EmitObject("polyline", group+"::Centerlines", tuple(points), tags))
        for j, (a, b) in enumerate(zip(points, points[1:])):
            if math.dist(a, b) < 1e-9:
                continue
            st = {k: v for k, v in tags.items() if k != "clash.group"}
            st.update({"bim.id": tags["bim.id"]+f"-solid-{j}", "bim.type": "steel_envelope"})
            add(EmitObject("cylinder", group+"::Solids", (a, b), st, radius_ft=diameter/24))

    # Existing section/strand definitions, with paired bearings and inclined beams.
    for o in base.objects:
        if o.tags.get("bim.type") in ("deck", "tie_rod", "diaphragm"):
            continue
        tags = {k: v for k, v in o.tags.items() if not k.startswith("pay.")}
        tags["bim.id"] = prefix+"-"+tags.get("bim.id", "reference")
        if tags.get("bim.type") == "bearing":
            tags["bearing.fixity"] = "fixed" if inp.abutment == "integral" else "expansion"
        add(replace(o, points=tuple((x, y, z+beam_z(x, y)) for x, y, z in o.points), tags=tags))

    ties = diaphragm_stations_ft(span, 27)
    rod_stations = tuple(x+offset for x in ties for offset in (-.5, -.25, 0., .25, .5))
    posts = post_stations(span, rod_stations) if inp.railing == "TST-2" else tuple(1.75+i*5.65 for i in range(11))
    # End blocks and intermediate solid diaphragms are within each hollow beam.
    for i in range(8):
        for j, x in enumerate(ties):
            half = 1.625 if j in (0, len(ties)-1) else .75
            x0, x1 = (0., 3.25) if j == 0 else ((span-3.25, span) if j == len(ties)-1 else (x-half, x+half))
            solid(f"B{i}-BLOCK{j}", "diaphragm", x0, x1, 4*i+.5, 4*i+3.5,
                  5.5/12, depth-5.5/12, "PSBD-1-25")
    # Overlapping groups of <=3 beams; rods remain straight across the crown.
    for j, x in enumerate(ties):
        for k, (a, b) in enumerate(((0, 3), (2, 4), (3, 5), (4, 7), (6, 8))):
            xx = x+(k-2)*.25
            ya, yb = 4*a+.25, 4*b-.25
            bar(f"TIE{j}-{k}", "tie_rods", ((xx, ya, .75+beam_z(xx, ya)),
                (xx, yb, .75+beam_z(xx, yb))), diameter=1., source="PSBD-1-25")

    # Topping follows the roadway profile, while beams retain straight grades.
    halves = ((0., 16.), (16., 32.)) if inp.crown else ((0., width),)
    ys = (0., 16., width) if inp.crown else (0., width)
    sections = []
    for i in range(61):
        x = float(i)
        sections.append(tuple((x,y,depth+beam_z(x,y)) for y in ys)
                        + tuple((x,y,road(x,y)) for y in reversed(ys)))
    add(swept_solid("deck", sections, tag("deck", "TOPPING", "BDM 308.3",
                                        **{"geometry.native": "station_loft"})))
    # #6 transverse over longitudinal: 2.5 in top cover, tangent tied mat.
    for i in range(81):
        x = .3+i*(span-.6)/80
        ys = [.3, 16., width-.3] if inp.crown else [.3, width-.3]
        bar(f"DECK-T{i}", "deck_rebar", [(x, y, road(x, y)-2.875/12) for y in ys], 6, "BDM 308.3")
    for i in range(23):
        y = .3+i*(width-.6)/22
        bar(f"DECK-L{i}", "deck_rebar", [(x, y, road(x, y)-3.625/12)
            for x in [.3]+[float(j) for j in range(2, 60, 2)]+[59.7]], 6, "BDM 308.3")

    # Beam top longitudinal bars and fascia stirrup envelopes for rod clashes.
    for i in range(8):
        for k, y in enumerate((4*i+.2, 4*i+.45, 4*i+3.55, 4*i+3.8)):
            z = depth-1.6/12
            bar(f"BEAM{i}-L{k}", "beam_rebar", [(x, y, z+beam_z(x, y)) for x in (.2, 59.8)], 5, "TST-2-21")
        xs = [.3+j*.5 for j in range(120)]
        if i in (0, 7):
            xs = [x for x in xs if all(abs(x-p) > .55 for p in posts)]
            anchor_xs = [p+dx for p in posts for dx in (-8/12, 8/12)]
            xs = [min((a for a in anchor_xs if abs(x-a) < .12), default=x)+.15
                  if any(abs(x-a) < .12 for a in anchor_xs) else x for x in xs]
            xs += [p+offset for p in posts for offset in (-.375, -.375-1/24, .375, .375+1/24)]
        for j, x in enumerate(sorted(xs)):
            a, b, lo, hi = 4*i+.14, 4*i+3.86, .14, depth-.14
            points = [(x, y, z+beam_z(x, y)) for y, z in ((a, lo), (b, lo), (b, hi), (a, hi), (a, lo))]
            bar(f"BEAM{i}-ST{j}", "beam_rebar", points, 4, "PSBD-1-25 / TST-2-21")

    # Open side-mounted railing. Rail solids are four walls, not solid tubes.
    for side, edge, inward in ((("L", 0., 1), ("R", width, -1)) if inp.railing == "TST-2" else ()):
        for k, (bottom, height, breadth) in enumerate(((12, 8, 6), (23, 8, 6), (35, 4, 12))):
            yc = edge+inward*breadth/24
            ya, yb = yc-breadth/24, yc+breadth/24
            t = .25/12
            for j in range(30):
                x0, x1 = j*2., (j+1)*2.
                for wall, a, b, lo, hi in (("B", ya, yb, bottom/12, bottom/12+t),
                    ("T", ya, yb, (bottom+height)/12-t, (bottom+height)/12),
                    ("L", ya, ya+t, bottom/12+t, (bottom+height)/12-t),
                    ("R", yb-t, yb, bottom/12+t, (bottom+height)/12-t)):
                    solid(f"RAIL{side}-{k}-{j}-{wall}", "railing", x0, x1, a, b, lo, hi,
                          "TST-2-21", surface=lambda x, y, edge=edge: road(x, edge))
        section = girder_section("W6X15")
        for j, x in enumerate(posts):
            yc = edge-inward*.3
            zbase = road(x, edge)+39/12-60.375/12
            # Web across the bridge, post flange faces parallel traffic.
            pts = tuple((x+w/12, yc+(h-section.depth/2)/12, zbase)
                        for w, h in i_profile_wh(section))
            add(EmitObject("prism", "railing", pts, tag("railing_post", f"POST{side}{j}", "TST-2-21"),
                           vector=(0, 0, 60.375/12)))
            for k, dx in enumerate((-8/12, 8/12)):
                xx = x+dx
                # f5: two 32 in transverse rods per post, through top flange.
                z = depth-2.75/12+beam_z(xx, edge)
                bar(f"F5-{side}{j}-{k}", "rail_anchors", [(xx, edge-inward*.2, z),
                    (xx, edge+inward*(32/12-.2), z)], diameter=1., source="TST-2-21 sheet 2")
                for m, dz in enumerate((0., -11/12)):
                    bar(f"F4-{side}{j}-{k}-{m}", "rail_short_anchors", [(xx, edge-inward*.15, z+dz),
                        (xx, edge+inward*(4/12-.15), z+dz)], diameter=1., source="TST-2-21")
            solid(f"F1-{side}{j}", "railing_plates", x-10/12, x+10/12,
                  min(edge, edge-inward*.04), max(edge, edge-inward*.04),
                  depth-15.75/12, depth-.75/12, "TST-2-21")

    for end, origin, sign in (("S", 0., -1), ("E", span, 1)):
        # u positive toward embankment. Bearing CL is .5 ft inside beam end.
        def xp(u):
            return origin+sign*u

        def block(ident, kind, ua, ub, ya, yb, za, zb, source):
            solid(end+ident, kind, min(xp(ua), xp(ub)), max(xp(ua), xp(ub)),
                  ya, yb, za, zb, source)

        cap_bottom = -3.5-pad_t
        block("CAP", "abutment_cap", -2., 1., -1., width+1, cap_bottom, -pad_t, "BDM 306")
        if inp.abutment != "integral":
            half = 5. if foundation == "spread" else 3.
            block("FOOT", "spread_footing" if foundation == "spread" else "foundation",
                  -.5-half, -.5+half, -2., width+2, cap_bottom-2.5, cap_bottom, "ASSUMED")
            # Transverse/longitudinal footing mat. Sizes are explicit assumed
            # coordination geometry, not a replacement for foundation design.
            for k in range(35):
                y = -1.+k
                bar(f"{end}-FOOT-T{k}", "footing_rebar", [(xp(u),y,cap_bottom-2.2+beam_z(xp(u),y))
                    for u in (-half-.2, half-.8)], 8, "ASSUMED")
            for k in range(int(2*half)):
                u = -half+.05+k
                bar(f"{end}-FOOT-L{k}", "footing_rebar", [(xp(u),y,cap_bottom-2.1+beam_z(xp(u),y))
                    for y in (-1.7,16.,width+1.7)], 8, "ASSUMED")
        # Integral backwall continuous with pile cap; semi-integral diaphragm
        # isolated above cap; conventional backwall behind an expansion joint.
        gap = 2/12 if inp.abutment == "seat" else 0.
        bottom = -pad_t if inp.abutment != "semi-integral" else .08
        block("BACKWALL", "abutment_backwall", gap, 1.25+gap, -1., width+1,
              bottom, depth+7/12, "A-1-20" if inp.abutment == "seat" else "BDM Fig 306-7/8")
        bridge_limit = 1.25+gap
        approach = layout_approach_slab(ApproachSlabInput(inp.approach_length_ft, width,
                                     seat_length_in=9, backwall_thickness_in=15))
        thick = approach.design.thickness_in/12
        block("SEAT", "approach_seat", bridge_limit, bridge_limit+.75, 0, width,
              depth+7/12-thick-.75, depth+7/12-thick, "AS-1-15")
        if inp.abutment != "integral":
            for side, ya, yb in (("L", -1.5, -1/6), ("R", width+1/6, width+1.5)):
                block("WING"+side, "wingwall", 1., 11., ya, yb, cap_bottom, depth+.5, "ASSUMED")
        rows = ((-.5,) if inp.abutment == "integral" else (-2., 1.)) if foundation == "piles" else ()
        hp = girder_section("HP10X42")
        for row, u in enumerate(rows):
            for k in range(6):
                y = 1.+k*6
                head = -pad_t-1.5 if inp.abutment == "integral" else cap_bottom-.5
                # HP web parallel to bearing CL; flange width along roadway.
                pts = tuple((xp(u)+w/12, y+(h-hp.depth/2)/12, head+beam_z(xp(u), y))
                            for w, h in i_profile_wh(hp))
                add(EmitObject("prism", "piles", pts, tag("pile", f"{end}-PILE{row}-{k}", "BDM 306", length_ft=30), vector=(0,0,-30)))
        if foundation == "shafts":
            for k,y in enumerate((3.,16.,29.)):
                x = xp(-.5)
                top = cap_bottom-.5+beam_z(x,y)
                add(EmitObject("cylinder", "drilled_shafts", ((x,y,top-15.),(x,y,top)),
                               tag("drilled_shaft", f"{end}-SHAFT{k}", "ASSUMED", diameter_in=42), radius_ft=1.75))
                for j in range(12):
                    theta = 2*math.pi*j/12
                    xx,yy = x+1.43*math.cos(theta),y+1.43*math.sin(theta)
                    bar(f"{end}-SHAFT{k}-L{j}", "shaft_rebar", ((xx,yy,top-14.7),(xx,yy,top+.25)), 8, "ASSUMED")
                for j in range(29):
                    z = top-14.5+j*.5
                    points = [(x+1.5*math.cos(t*math.pi/16),y+1.5*math.sin(t*math.pi/16),z) for t in range(33)]
                    bar(f"{end}-SHAFT{k}-H{j}", "shaft_rebar", points, 4, "ASSUMED")
        # Cap main bars and backwall cage. Actual envelopes checked against
        # the approach anchors rather than deleting bars to conceal conflicts.
        for row, u in enumerate((-.5, .5)):
            for j, z in enumerate((cap_bottom+.3, -pad_t-.3)):
                ys = [-.7, 16., width+.7] if inp.crown else [-.7, width+.7]
                bar(f"{end}-CAP{row}-{j}", "abutment_rebar", [(xp(u), y, z+beam_z(xp(u), y)) for y in ys], 8, "ASSUMED")
        for face, u in enumerate((gap+.22, gap+1.03)):
            for j in range(34):
                y = -.5+j
                bar(f"{end}-BWV{face}-{j}", "abutment_rebar", [(xp(u), y, z+beam_z(xp(u), y))
                    for z in (bottom+.22, depth+7/12-.22)], 5, "ASSUMED")
            for j in range(4):
                z = bottom+.25+j*.7
                ys = [-.5, 16., width+.5] if inp.crown else [-.5, width+.5]
                bar(f"{end}-BWH{face}-{j}", "abutment_rebar", [(xp(u), y, z+beam_z(xp(u), y)) for y in ys], 5, "ASSUMED")
        for i in range(8):
            x, y = xp(-.5), 4*i+2
            bar(f"{end}-DOWEL{i}", "bearing_dowels", [(x, y, z+beam_z(x, y)) for z in (-1., depth-.25)],
                diameter=1., source="PSBD-1-25")

        def apoint(p, offset=0.):
            u, y, z = p
            x = xp(bridge_limit+u+offset)
            return (x, y, z+road(x, y))

        for j, (ya, yb) in enumerate(halves):
            pts = tuple(apoint((u, ya, z)) for u, z in approach.profile)
            add(EmitObject("prism", "approach_slab", pts, tag("approach_slab", f"{end}-APS{j}", "AS-1-15"),
                           vector=(0, yb-ya, cross(yb)-cross(ya))))
        for j, b in enumerate(approach.bars):
            pts = list(b.points)
            if inp.crown and len(pts) == 2 and pts[0][1] < 16 < pts[-1][1]:
                a, c = pts
                f = (16-a[1])/(c[1]-a[1])
                pts.insert(1, tuple(a[k]+f*(c[k]-a[k]) for k in range(3)))
            bar(f"{end}-APS-{b.mark}-{j}", "approach_anchors" if b.mark.startswith("D") else "approach_rebar",
                [apoint(p) for p in pts], b.size, "AS-1-15")
        sleeper = layout_sleeper_slab(SleeperSlabInput(width_ft=width, installation="A"))
        for j, (ya, yb) in enumerate(halves):
            pts = tuple(apoint((u, ya, -thick+z), inp.approach_length_ft)
                        for u, z in ((-4., 0.), (4., 0.), (4., -sleeper.thickness_in/12), (-4., -sleeper.thickness_in/12)))
            add(EmitObject("prism", "sleeper", pts, tag("sleeper", f"{end}-SLEEP{j}", "AS-2-15"),
                           vector=(0, yb-ya, cross(yb)-cross(ya))))
        for j, b in enumerate(sleeper.bars):
            local = list(b.points)
            if inp.crown and local[0][1] < 16 < local[-1][1]:
                a, c = local
                f = (16-a[1])/(c[1]-a[1])
                local.insert(1, tuple(a[k]+f*(c[k]-a[k]) for k in range(3)))
            pts = [apoint((u, y, z-thick), inp.approach_length_ft) for u, y, z in local]
            bar(f"{end}-SS{j}", "sleeper_rebar", pts, b.size, "AS-2-15")
        drain = [apoint((u, y, z-thick), inp.approach_length_ft) for u, y, z in sleeper.underdrain]
        add(EmitObject("cylinder", "drainage", tuple(drain), tag("underdrain", f"{end}-DRAIN", "AS-2-15"), radius_ft=.25))

    # Visible surface-flow traces; no raised curb or forbidden underside groove.
    for x in (10., 30., 50.):
        for y0, y1 in ((15.8, 0.), (16.2, width)) if inp.crown else ((0., width),):
            add(EmitObject("polyline", "drainage", ((x,y0,road(x,y0)+.03),
                (x,y1,road(x,y1)+.03), (x,y1,road(x,y1)-.5)), tag("flow_path", f"FLOW{x}-{y0}")))
    from civilpy.structural.box_bridge_railing import railing_and_approaches
    objects.extend(railing_and_approaches(inp, road, beam_z, posts))
    return BridgeEmit(inp, None, tuple(objects), {
        "bim.units": "ft", "bim.family": "box", "detail.abutment": inp.abutment,
        "detail.foundation": foundation, "detail.railing": inp.railing, "detail.terminal": inp.terminal,
        "detail.traffic": "one-way +X" if inp.terminal == "trailing_t" else "two-way non-NHS local road",
        "detail.status": "coordination example - unresolved details, not construction design",
        "detail.limitations": " | ".join(LIMITATIONS), "detail.post_stations_ft": str(posts),
        "detail.topping_range_in": f"7..{7+inp.profile_rise_in:g}",
        "detail.profile_grade_pct": str(inp.grade_pct), "detail.crossfall_pct": str(inp.crossfall_pct)})
