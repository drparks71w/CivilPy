"""DBR retrofit railing, bridge transitions, and roadside end-treatment envelopes.

Dimensions cite the locally cached ODOT drawings. Corrugations are sampled
nominal envelopes; bolt slots, thread forms and fabrication tolerances are not
represented. Type T is emitted only at the downstream end of an explicitly
one-way scenario. Type A examples assume a restricted, non-NHS local route.
"""
from __future__ import annotations

import math

from civilpy.structural.bridge_layout import girder_section
from civilpy.structural.detail_geometry import swept_solid
from civilpy.structural.rhino_bim import EmitObject, i_profile_wh
from civilpy.structural.rhino_box_bim import _rect_prism


def corrugated_section(waves=2, height_in=12.25, thickness_in=.1046, samples=48):
    """Closed nominal W/thrie sheet envelope in (outward, vertical) feet."""
    front = [(3.25/24*(1+math.cos(waves*2*math.pi*i/samples)),
              height_in/12*(i/samples-.5)) for i in range(samples+1)]
    return tuple(front+[(q+thickness_in/12,z) for q,z in reversed(front)])


def railing_and_approaches(inp, road, beam_z, bridge_posts):
    prefix = inp.scenario_id or inp.abutment
    objects = []

    def tags(kind, ident, source, **extra):
        return {"bim.type":kind, "bim.id":prefix+"-"+ident, "bim.scd":source,
                **{k:str(v) for k,v in extra.items()}}

    def add(obj):
        from dataclasses import replace
        objects.append(replace(obj, layer=prefix+"::"+obj.layer))

    def box(ident, layer, bounds, source, kind=None):
        add(_rect_prism(layer, *bounds, tags(kind or layer,ident,source)))

    def cylinder(ident, layer, a, b, diameter_in, source, kind=None):
        add(EmitObject("cylinder",layer,(a,b),tags(kind or layer,ident,source),radius_ft=diameter_in/24))

    def wpost(ident, x, y, top, length, shape, source, kind="roadside_post"):
        section = girder_section(shape)
        points = tuple((x+w/12,y+(h-section.depth/2)/12,top-length) for w,h in i_profile_wh(section))
        add(EmitObject("prism","railing_posts",points,
                       tags(kind,ident,source,shape=shape,length_ft=length),vector=(0,0,length)))

    def sheet(ident, layer, path, source, thickness=.1046, kind="guardrail_panel"):
        # path entries: x, y (front face), center elevation, outward sign,
        # W-to-thrie blend, section rotation about the longitudinal axis.
        rings = []
        w = corrugated_section(2,12.25,thickness)
        thrie = corrugated_section(3,20.,thickness)
        for x,y,z,out,blend,angle in path:
            ca,sa = math.cos(angle),math.sin(angle)
            ring = []
            for (qw,zw),(qt,zt) in zip(w,thrie):
                q,h = qw*(1-blend)+qt*blend, zw*(1-blend)+zt*blend
                ring.append((x,y+out*(q*ca+h*sa),z+h*ca-q*sa))
            rings.append(ring)
        add(swept_solid(layer,rings,tags(kind,ident,source,thickness_in=thickness)))

    def tube(ident, path, width_in, height_in, source, wall_in=.1875):
        # path centerline entries (x,y,z); section remains upright, so the
        # path supports the DBR top taper and the lower 15-degree plan flare.
        w,h,t = width_in/24,height_in/24,wall_in/12
        for name,a,b,c,d in (("B",-w,w,-h,-h+t),("T",-w,w,h-t,h),
                              ("L",-w,-w+t,-h+t,h-t),("R",w-t,w,-h+t,h-t)):
            rings = [((x,y+a,z+c),(x,y+b,z+c),(x,y+b,z+d),(x,y+a,z+d)) for x,y,z in path]
            add(swept_solid("railing",rings,tags("railing_tube",ident+name,source,
                            width_in=width_in,height_in=height_in)))

    for side,edge,out in (("L",0.,-1), ("R",32.,1)):
        face = edge-out*2/3 if inp.railing == "DBR-3" else edge
        if inp.railing == "DBR-3":
            first,last = bridge_posts[0],bridge_posts[-1]
            # DBR-2 Type 2 W6x25 posts for box beams; DBR-3 retrofit adds
            # upper and lower tubes behind the corrugated traffic face.
            for j,x in enumerate(bridge_posts):
                y = edge+out*.3
                z = road(x,edge)
                wpost(f"DBR-{side}-P{j}",x,y,z+25/12,4.8,"W6X25","DBR-2-73", "railing_post")
                for level in (21.,):
                    tube(f"DBR-{side}-SPACER{j}",[(x-.25,edge-out*.1,z+level/12+2/12),
                          (x+.25,edge-out*.1,z+level/12+2/12)],8,4,"DBR-2-73")
                # Existing Type B upper anchors and Type C lower insert.
                for k,dx in enumerate((-.16,.16)):
                    zz = 27/12-3/12+beam_z(x,edge)
                    a,b = (x+dx,edge+out*.65,zz),(x+dx,edge-out*15/12,zz)
                    cylinder(f"DBR-{side}-B{j}-{k}","rail_anchors::Solids",a,b,1.125,"DBR-2-73")
                    add(EmitObject("polyline","rail_anchors::Centerlines",(a,b),
                        tags("anchor",f"DBR-{side}-B{j}-{k}-CL","DBR-2-73",
                             **{"clash.group":"rail_anchors","rebar.dia_in":1.125})))
                zz = 27/12-11/12+beam_z(x,edge)
                cylinder(f"DBR-{side}-C{j}","rail_short_anchors",(x,edge+out*.4,zz),
                         (x,edge-out*8/12,zz),1.125,"DBR-2-73")
            start,end = first-6.25,last+6.25
            count = math.ceil((end-start)/12.5)
            for j in range(count):
                a,b = start+j*(end-start)/count,start+(j+1)*(end-start)/count
                xs = [a+(b-a)*k/8 for k in range(9)]
                sheet(f"DBR-{side}-W{j}","railing_corrugated",
                      [(x,face,road(x,edge)+(27.75-6.125)/12,out,0.,0.) for x in xs],"DBR-2-73 / DBR-3-11")
            for name,center in (("UPPER",27.),("LOWER",12.625)):
                tube(f"DBR-{side}-{name}",[(x,edge-out*.1,road(x,edge)+center/12)
                     for x in (first,*range(6,58,3),last)],8,4,"DBR-3-11")
            for end_name,first_x,sgn in (("S",first,-1), ("E",last,1)):
                x1,x2 = first_x+sgn*2,first_x+sgn*2.5
                tube(f"DBR-{side}-{end_name}-TOP-RETURN",
                     [(first_x,edge-out*.1,road(first_x,edge)+27/12),
                      (x1,edge-out*.1,road(x1,edge)+23/12),
                      (x2,edge-out*.1,road(x2,edge)+23/12)],8,4,"DBR-3-11 detail B/C")
                x1 = first_x+sgn*5*math.cos(math.radians(15))
                tube(f"DBR-{side}-{end_name}-LOWER-FLARE",
                     [(first_x,edge-out*.1,road(first_x,edge)+12.625/12),
                      (x1,edge-out*.1+out*5*math.sin(math.radians(15)),road(x1,edge)+12.625/12)],
                     8,4,"DBR-3-11 detail D")

        for end,origin,sgn in (("S",0.,-1), ("E",60.,1)):
            key = f"{side}-{end}"
            xof = lambda u: origin+sgn*u
            def center(u,top=31.,height=12.25):
                return road(xof(u),edge)+(top-height/2)/12

            def panel(ident,a,b,top_a=31.,top_b=31.,blend_a=0.,blend_b=0.,nested=False,source=None,kind="guardrail_panel"):
                path=[]
                for k in range(9):
                    f=k/8;u=a+(b-a)*f;mix=blend_a+(blend_b-blend_a)*f
                    top=top_a+(top_b-top_a)*f
                    path.append((xof(u),face,center(u,top,12.25+7.75*mix),out,mix,0.))
                source = source or ("GR-3.4" if inp.railing=="DBR-3" else "MGS-3.3")
                sheet(key+ident,"railing_transition",path,source,kind=kind)
                if nested:
                    sheet(key+ident+"-NESTED","railing_transition",
                          [(x,y+out*.11/12,z,o,m,a) for x,y,z,o,m,a in path],"GR-3.4" if inp.railing=="DBR-3" else "MGS-3.3")

            if inp.railing == "DBR-3":
                u0 = 6.25-bridge_posts[0]
                offsets=(0.,1.5625,3.125,4.6875,6.25,9.375,12.5,15.625,18.75,25.)
                for j,du in enumerate(offsets):
                    u=u0+du;x=xof(u);z=road(x,edge)
                    wpost(f"{key}-BTA4-P{j+1}",x,face+out*(8/12+.25),z+27.75/12,
                          6.,"W6X25" if j==0 else "W6X9","GR-3.4")
                    box(f"{key}-BTA4-BLOCK{j+1}","railing_blockouts",
                        (x-.25,x+.25,min(face,face+out*8/12),max(face,face+out*8/12),
                         center(u,27.75)-7/12,center(u,27.75)+7/12),"GR-3.4")
                    # Sheet legend: rail deliberately not attached at 2,3,4,6,8.
                    if j+1 not in (2,3,4,6,8):
                        cylinder(f"{key}-BTA4-BOLT{j+1}","railing_hardware",
                                 (x,face-out*.05,center(u,27.75)),(x,face+out*.9,center(u,27.75)),.625,"GR-3.4")
                panel("-BTA4-NEST",u0,u0+12.5,27.75,27.75,nested=True)
                panel("-BTA4-SINGLE",u0+12.5,u0+25,27.75,27.75)
                # Ramp 27.75 -> 31 in within four 12.5 ft panels, <=2 in/25 ft.
                ramp=u0+25
                for j in range(4):
                    panel(f"-HEIGHT{j}",ramp+12.5*j,ramp+12.5*(j+1),27.75+3.25*j/4,27.75+3.25*(j+1)/4,source="MGS-4.3")
                run_start=ramp
                terminal_start=ramp+50
            else:
                # Formed bridge-side adapters join the TST tubes to the
                # 20 in thrie beam, followed by the standard nested transition.
                join=4.5
                for j,(z0,z1,height) in enumerate(((16,18,8),(27,30,8),(37,34,4))):
                    tube(f"{key}-TST-ADAPTER{j}",[(xof(u),edge+out*.12,road(xof(u),edge)+z/12)
                         for u,z in ((0.,z0),(join,z1))],6 if j<2 else 12,height,"TST-2-21 sheet 7",.25)
                panel("-THRIE-NEST",join,join+12.5,34,34,1,1,nested=True)
                panel("-THRIE-SINGLE",join+12.5,join+18.75,34,34,1,1)
                panel("-THRIE-TO-W",join+18.75,join+25,34,31,1,0)
                offsets=(0.,3.125,6.25,7.8125,9.375,10.9375,12.5,15.625,18.75,21.875)
                for j,du in enumerate(offsets):
                    u=join+25-du;x=xof(u);top=31 if j<3 else 34
                    wpost(f"{key}-TST-BTA-P{j+1}",x,face+out*1.25,road(x,edge)+32/12,
                          6. if j<7 else 7.,"W6X9" if j<7 else "W6X15","MGS-3.3")
                    box(f"{key}-TST-BLOCK{j+1}","railing_blockouts",
                        (x-.25,x+.25,min(face,face+out),max(face,face+out),
                         center(u,top,12.25 if j<3 else 20)-.6,
                         center(u,top,12.25 if j<3 else 20)+.6),"MGS-3.3")
                run_start=join+25
                terminal_start=run_start+25
                for j in range(2):panel(f"-MGS{j}",run_start+j*12.5,run_start+(j+1)*12.5,source="MGS-2.1")

            for j in range(1,int(round((terminal_start-run_start)/6.25))+1):
                u=run_start+j*6.25;x=xof(u)
                top=31 if inp.railing=="TST-2" else 27.75+3.25*(u-run_start)/(terminal_start-run_start)
                wpost(f"{key}-MGS-P{j}",x,face+out*1.25,road(x,edge)+32/12,6.,"W6X9","MGS-2.1")
                box(f"{key}-MGS-BLOCK{j}","railing_blockouts",
                    (x-.25,x+.25,min(face,face+out),max(face,face+out),center(u,top)-.6,center(u,top)+.6),"MGS-2.1")

            terminal = inp.terminal
            if terminal == "trailing_t" and end == "S":
                terminal = "buried"  # one-way +X traffic; never an exposed upstream Type T
            if terminal == "type_a":
                # SCD MGS-4.1: 25 ft panel, 18'-9" post-slot-to-anchor,
                # gradually twisted 90 degrees into a 36 in concrete anchor.
                length=25.
                terminal_end=terminal_start+length
                path=[]
                for j in range(41):
                    f=j/40;u=terminal_start+length*f;x=xof(u)
                    yc=face+out*1.5*f
                    z=road(x,edge)+(31-6.125)/12*(1-f)-.2*f
                    path.append((x,yc,z,out,0.,math.pi/2*f*f*(3-2*f)))
                sheet(key+"-TYPE-A-RAIL","end_treatments",path,"MGS-4.1",kind="terminal_rail")
                for j,du in enumerate((0.,6.25)):
                    u=terminal_start+du;x=xof(u);z=road(x,edge)
                    wpost(f"{key}-TYPE-A-P{j}",x,face+out*.9,z+31/12,6.,"W6X9","MGS-4.1")
                x,y,z,_,_,_=path[-1]
                cylinder(key+"-TYPE-A-ANCHOR","terminal_concrete",(x,y,z-3.8),(x,y,z+.15),36,"MGS-4.1","terminal_anchor")
                for j in range(10):
                    theta=j*math.pi/5
                    xx,yy=x+1.3*math.cos(theta),y+1.3*math.sin(theta)
                    cylinder(f"{key}-TYPE-A-BAR{j}","terminal_rebar",(xx,yy,z-3.6),(xx,yy,z-.1),.375,"MGS-4.1")
                for j in range(7):
                    zz=z-3.5+j*.5
                    pts=tuple((x+1.32*math.cos(k*math.pi/16),y+1.32*math.sin(k*math.pi/16),zz) for k in range(33))
                    add(EmitObject("polyline","terminal_rebar",pts,tags("rebar",f"{key}-TYPE-A-HOOP{j}","MGS-4.1")))
                for dx in (-.25,.25):
                    cylinder(f"{key}-TYPE-A-BOLT{dx}","terminal_anchors",(x+dx,y,z-.8),(x+dx,y,z+.2),.875,"MGS-4.1")
            elif terminal == "trailing_t":
                length=12.5
                terminal_end=terminal_start+length
                panel("-TYPE-T-RAIL",terminal_start,terminal_start+length,source="MGS-4.2",kind="terminal_rail")
                # Wood BCT system: two breakaway posts, ground tube and
                # strut, cable back to the rail anchorage, rounded nose.
                us=(terminal_start+3.125,terminal_start+9.375)
                for j,u in enumerate(us):
                    x=xof(u);y=face+out*.4;z=road(x,edge)
                    box(f"{key}-TYPE-T-BCT{j}","terminal_timber",
                        (x-.25,x+.25,y-1/3,y+1/3,z-3.5,z+31/12),"MGS-4.2","breakaway_post")
                    for wall,xa,xb,ya,yb in (("L",x-.29,x-.25,y-.375,y+.375),
                        ("R",x+.25,x+.29,y-.375,y+.375),
                        ("F",x-.25,x+.25,y-.375,y-.333),
                        ("B",x-.25,x+.25,y+.333,y+.375)):
                        box(f"{key}-TYPE-T-GROUND{j}-{wall}","end_treatments",
                            (xa,xb,ya,yb,z-3.5,z+.1),"MGS-4.2")
                a,b=xof(us[0]),xof(us[1]);y=face+out*.4
                z=road(a,edge)+.15
                box(key+"-TYPE-T-STRUT","end_treatments",(min(a,b),max(a,b),y-.25,y+.25,z,z+.25),"MGS-4.2")
                cylinder(key+"-TYPE-T-CABLE","end_treatments",(b,y,road(b,edge)+.3),
                         (xof(terminal_start+4),y,center(terminal_start+4)),.75,"MGS-4.2")
                box(key+"-TYPE-T-BEARING-PLATE","terminal_hardware",
                    (b-.02,b+.02,y-1/3,y+1/3,road(b,edge)+.3-1/3,road(b,edge)+.3+1/3),"MGS-4.2")
                bracket_x=xof(terminal_start+4)
                box(key+"-TYPE-T-CABLE-BRACKET","terminal_hardware",
                    (bracket_x-.35,bracket_x+.35,y-.05,y+.05,
                     center(terminal_start+4)-.21,center(terminal_start+4)+.21),"MGS-4.2")
                # Return the terminal sheet away from traffic; no raw rail end.
                u=terminal_start+length;x=xof(u);z=center(u);r=.55
                rings=[]
                for j in range(25):
                    t=math.pi*j/24
                    xx=x+sgn*r*math.sin(t);yy=face+out*r*(1-math.cos(t))
                    nx,ny=sgn*math.sin(t),-out*math.cos(t)
                    rings.append(((xx,yy,z-.7),(xx+nx*.009,yy+ny*.009,z-.7),
                                  (xx+nx*.009,yy+ny*.009,z+.7),(xx,yy,z+.7)))
                add(swept_solid("end_treatments",rings,tags("rounded_terminal",key+"-TYPE-T-NOSE","MGS-4.2")))
            else:
                # MGS-4.5 plan lengths and offsets. Last two bays are half
                # spacing. The terminal is actually buried under a soil bank.
                lengths=(74+10/12,24+9.5/12,12+4/12,12+1/12)
                offsets=(5.75,8+10.25/12,10+11/12,13+11.75/12)
                knots=[(0.,0.)]
                for length,offset in zip(lengths,offsets):knots.append((knots[-1][0]+length,offset))
                end_u=knots[-1][0]
                terminal_end=terminal_start+end_u
                def offset_at(s):
                    for (a,ya),(b,yb) in zip(knots,knots[1:]):
                        if s<=b:return ya+(yb-ya)*(s-a)/(b-a)
                    return knots[-1][1]
                def burial(s):
                    return max(0.,min(1.,(s-knots[1][0])/(end_u-knots[1][0])))
                xs=sorted(set([i*end_u/64 for i in range(65)]+[x for x,y in knots]))
                path=[]
                for s in xs:
                    u=terminal_start+s;x=xof(u);y=face+out*offset_at(s)
                    path.append((x,y,center(u)-16/12*burial(s),out,0.,0.))
                sheet(key+"-BURIED-RAIL","end_treatments",path,"MGS-4.5",kind="terminal_rail")
                stations=[0.]
                while stations[-1]<end_u-6.25:
                    stations.append(min(stations[-1]+6.25,end_u-6.25))
                stations.extend((end_u-3.125,end_u))
                for j,s in enumerate(stations):
                    u=terminal_start+s;x=xof(u);y=face+out*(offset_at(s)+1.)
                    top=road(x,edge)+32/12-16/12*burial(s)
                    wpost(f"{key}-BURIED-P{j}",x,y,top,6.,"W6X9","MGS-4.5")
                # 12 in cover over the top of the buried rail at its end.
                bank=[]
                for s in (knots[1][0],end_u):
                    u=terminal_start+s;x=xof(u);y=face+out*offset_at(s)
                    top=road(x,edge)+2.25*burial(s)
                    bank.append(((x,y-3,top-3),(x,y+3,top-3),(x,y+3,top),(x,y-3,top)))
                add(swept_solid("terminal_soil_bank",bank,tags("soil_bank",key+"-BACKSLOPE","MGS-4.5",cover_in=12)))
                x,y,z,_,_,_=path[-1]
                box(key+"-BURIED-ANCHOR-PLATE","terminal_anchors",
                    (x-.03,x+.03,y-.5,y+.5,z-.75,z+.75),"MGS-4.5","buried_anchor_plate")
                # Rub rail along the last three posts, per sheet 1 detail D.
                s0=end_u-6.25
                sheet(key+"-BURIED-RUB","end_treatments",
                      [(xof(terminal_start+s),face+out*offset_at(s),center(terminal_start+s)-16/12*burial(s)-.8,out,0.,0.)
                       for s in (s0,end_u-3.125,end_u)],"MGS-4.5")
            if side == "L":
                # Context pavement meets the approach slab and extends through
                # the treatment. Hidden soil context supports the driven posts
                # and can be enabled for the full roadside installation view.
                approach_end=1.25+(2/12 if inp.abutment=="seat" else 0.)+inp.approach_length_ft
                ys=(0.,16.,32.) if inp.crown else (0.,32.)
                rings=[]
                for u in (approach_end,terminal_end+10):
                    x=xof(u)
                    rings.append(tuple((x,y,road(x,y)-.5) for y in ys)
                                 +tuple((x,y,road(x,y)) for y in reversed(ys)))
                add(swept_solid("roadway_context",rings,tags("pavement",end+"-PAVEMENT","CONTEXT")))
                soil=[]
                for u in (1.5,terminal_end+15):
                    x=xof(u)
                    soil.append(((x,-12,road(x,0)-8),(x,44,road(x,32)-8),
                                 (x,44,road(x,32)-4),(x,32,road(x,32)-.5),
                                 (x,0,road(x,0)-.5),(x,-12,road(x,0)-4)))
                add(swept_solid("terrain_context",soil,tags("soil",end+"-APPROACH-FILL","CONTEXT")))
            add(EmitObject("point","detail_labels",((xof(terminal_start),face,road(xof(terminal_start),edge)+4),),
                tags("terminal",key+"-TERMINAL", "MGS-4.1" if terminal=="type_a" else "MGS-4.2" if terminal=="trailing_t" else "MGS-4.5",
                     terminal_type=terminal,traffic="one-way +X" if inp.terminal=="trailing_t" else "two-way local non-NHS",end=end)))
    return tuple(objects)
