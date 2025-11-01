"""
Lookup bridge deck parameters from Ohio DOT standards
Inputs: span_length (int), continuous_span (bool), over_side_drainage (bool)
Outputs: thickness, bar parameters, top_cover, drainage/parapet parameters
"""

import argparse
import sys
from civilpy.state.ohio.DOT.bridge import simple_concrete_slab, continuous_concrete_slab
import math
# Removed System import - no longer needed


def get_deck_parameters(span_length: int, continuous_span: bool = False, over_side_drainage: bool = True) -> dict:
    """
    Retrieve bridge deck parameters based on span length and bridge type.

    Args:
        span_length: Span length in feet (int)
        continuous_span: Whether to use continuous span data (default: False for simple span)
        over_side_drainage: Whether to use over_side_drainage (True) or parapet (False) parameters

    Returns:
        Dictionary containing all deck parameters
    """
    # Select appropriate data dictionary
    data = continuous_concrete_slab if continuous_span else simple_concrete_slab

    # Check if span length exists
    if span_length not in data:
        available = sorted(data.keys())
        raise ValueError(
            f"Span length {span_length} ft not available. "
            f"Available spans: {available[0]}-{available[-1]} ft"
        )

    # Get parameters
    params = data[span_length]
    thickness = params['thickness']

    # ODOT standard concrete cover for bridge decks
    # This is a general value; specific bars (like A-bars) might have different requirements
    top_cover = 2.0  # inches

    # Select drainage or parapet type
    edge_type = 'over_side_drainage' if over_side_drainage else 'parapet'
    edge_params = params[edge_type]

    # Build result dictionary based on bridge type
    result = {
        'span_length': span_length,
        'bridge_type': 'continuous' if continuous_span else 'simple',
        'thickness': thickness,
        'top_cover': top_cover,  # General top cover
        'edge_type': edge_type,
    }

    # Extract bar parameters based on bridge type
    if not continuous_span:
        # Simple span - flat structure
        result['a_bar_spacing'] = params['a_bar_spacing']
        result['a_bar_size'] = params['a_bar_size']
        result['b_bar_spacing'] = params['b_bar_spacing']
        result['b_bar_size'] = params['b_bar_size']
        result['m_bar_spacing'] = params['m_bar_spacing']
        result['m_bar_size'] = params['m_bar_size']
        result['n_bar_spacing'] = params['n_bar_spacing']
        result['n_bar_size'] = params['n_bar_size']

        # Edge details for simple span
        result['edge_d'] = edge_params['d']
        result['edge_x'] = edge_params['x']
        result['d_bar_size'] = edge_params.get('d_bar_size', 0)
        result['d_bar_num'] = edge_params.get('d_bar_num', 0)
        result['e_bar_size'] = edge_params.get('e_bar_size', 0)
        result['e_bar_num'] = edge_params.get('e_bar_num', 0)
    else:
        # Continuous span - nested structure
        result['a_bar_spacing'] = params['a_bar']['spacing']
        result['a_bar_size'] = params['a_bar']['size']
        result['b_bar_spacing'] = params['b_bar']['spacing']
        result['b_bar_size'] = params['b_bar']['size']
        result['m_bar_spacing'] = params['m_bar']['spacing']
        result['m_bar_size'] = params['m_bar']['size']
        result['n_bar_spacing'] = params['n_bar']['spacing']
        result['n_bar_size'] = params['n_bar']['size']

        # Additional bars for continuous span
        if 'a' in params['a_bar']:
            result['a_bar_a'] = params['a_bar']['a']
        if 'length' in params['a_bar']:
            result['a_bar_length'] = params['a_bar']['length']
        if 'length' in params['b_bar']:
            result['b_bar_length'] = params['b_bar']['length']
        if 'no' in params['m_bar']:
            result['m_bar_no'] = params['m_bar']['no']
        if 'no' in params['n_bar']:
            result['n_bar_no'] = params['n_bar']['no']

        # C, D, E bars for continuous span
        if 'c_bar' in params:
            result['c_bar_spacing'] = params['c_bar']['spacing']
            result['c_bar_size'] = params['c_bar']['size']
            result['c_bar_length'] = params['c_bar']['length']
        if 'd_bar' in params:
            result['d_bar_spacing'] = params['d_bar']['spacing']
            result['d_bar_size'] = params['d_bar']['size']
            result['d_bar_length'] = params['d_bar']['length']
        if 'e_bar' in params:
            result['e_bar_spacing'] = params['e_bar']['spacing']
            result['e_bar_size'] = params['e_bar']['size']
            result['e_bar_length'] = params['e_bar']['length']

        # U bar lap
        if 'u_bar_lap' in params:
            result['u_bar_lap'] = params['u_bar_lap']

        # Edge details for continuous span
        result['edge_d'] = edge_params['d']
        result['edge_x'] = edge_params['x']

        # F, G, H, J, K bars for continuous edge
        for bar_letter in ['f_bar', 'g_bar', 'h_bar', 'j_bar', 'k_bar']:
            if bar_letter in edge_params:
                bar = edge_params[bar_letter]
                result[f'{bar_letter}_size'] = bar['size']
                result[f'{bar_letter}_no'] = bar['no']
                result[f'{bar_letter}_length'] = bar['length']
                if 'f' in bar and bar_letter == 'f_bar':
                    result['f_bar_f'] = bar['f']

    return result


def print_parameters(params: dict) -> None:
    """Pretty print the retrieved parameters."""
    print(f"\n{'='*60}")
    print(f"Bridge Deck Parameters - {params['bridge_type'].upper()} SPAN")
    print(f"Edge Type: {params['edge_type'].replace('_', ' ').title()}")
    print(f"{'='*60}")
    print(f"Span Length:              {params['span_length']} ft")
    print(f"Deck Thickness:           {params['thickness']} in")
    print(f"Concrete Cover:           {params['top_cover']} in")
    print(f"\n{'Main Rebar Configuration:':<40}")
    print(f"  Transverse (A) Bar:     #{params['a_bar_size']} @ {params['a_bar_spacing']}\" o.c.")
    print(f"  Transverse (B) Bar:     #{params['b_bar_size']} @ {params['b_bar_spacing']}\" o.c.")
    print(f"  Longitudinal (M) Bar:   #{params['m_bar_size']} @ {params['m_bar_spacing']}\" o.c.")
    print(f"  Longitudinal (N) Bar:   #{params['n_bar_size']} @ {params['n_bar_spacing']}\" o.c.")
    print(f"{'='*60}\n")


def get_aci_bend_radius(bar_size: int) -> float:
    """
    Get the ACI 318 minimum bend radius *to the centerline of the bar*.
    (ACI specifies *inside* bend radius, so we add 0.5 * diameter)

    Args:
        bar_size: Bar size number (e.g., 8 for #8)

    Returns:
        Centerline bend radius in inches
    """
    bar_diameter = bar_size / 8.0
    inside_bend_radius = 0.0

    if bar_size >= 3 and bar_size <= 8:
        # ACI 318-14 Table 25.3.2: 6 * db
        inside_bend_radius = 6 * bar_diameter
    elif bar_size >= 9 and bar_size <= 11:
        # ACI 318-14 Table 25.3.2: 8 * db
        inside_bend_radius = 8 * bar_diameter
    elif bar_size >= 14 and bar_size <= 18:
        # ACI 318-14 Table 25.3.2: 10 * db
        inside_bend_radius = 10 * bar_diameter
    else:
        # Default for #2 or other small bars
        inside_bend_radius = 6 * bar_diameter

    # Return centerline radius
    centerline_bend_radius = inside_bend_radius + 0.5 * bar_diameter
    return centerline_bend_radius


def generate_a_bars(span_length, a_bar_size, a_bar_spacing, deck_thickness, deck_width=24.0, bot_cover=1.5, top_cover=2.0):
    """
    Generate A-bar geometry (bottom tensile bars running transverse across span).
    A-bars have 180-degree development hooks at both ends per ACI 318.
    This "U-hook" is formed by two 90-degree bends.

    This is the version that produced the "Closer," image (ee6221.png)

    Args:
        span_length: Span length in feet
        a_bar_size: Bar size number (diameter in 8ths of inch)
        a_bar_spacing: Spacing in inches
        deck_thickness: Total slab thickness in inches
        deck_width: Bridge deck width in feet (default: 24')
        bot_cover: Bottom concrete cover in inches (default: 1.5")
        top_cover: Top concrete cover in inches (default: 2.0")

    Returns:
        List of Rhino Breps (pipes) or None if not in Rhino environment
    """
    # Calculate bar diameter in inches
    bar_diameter = a_bar_size / 8.0

    # Get ACI hook geometry
    centerline_bend_radius = get_aci_bend_radius(a_bar_size)

    # ACI 318-14 25.3.3.1: 180-deg hook extension
    # 4db or 2.5 in. min.
    hook_extension_length = max(4 * bar_diameter, 2.5)

    # Convert dimensions to inches
    span_length_in = span_length * 12.0
    deck_width_in = deck_width * 12.0

    # Number of bars across the deck width
    num_bars = int(deck_width_in / a_bar_spacing) + 1

    # Bar elevation (bottom of deck + cover + radius)
    # This is the centerline of the main straight portion of the bar.
    bar_elevation = bot_cover + bar_diameter / 2.0

    # Check if deck is thick enough for hooks
    # Calculate the Z-coordinate of the very top of the hook (top of the "U")
    hook_top_z = bar_elevation + 2 * centerline_bend_radius

    # Calculate the maximum Z-coordinate allowed (bottom of top cover)
    slab_top_clear_z = deck_thickness - top_cover

    if hook_top_z > slab_top_clear_z:
        print(
            f"Warning: A-Bar 180-deg hook top ({hook_top_z:.2f}\") may conflict with top cover "
            f"(clearance ends at {slab_top_clear_z:.2f}\" from bottom) "
            f"in {deck_thickness}\" slab."
        )

    # Try to create Rhino geometry
    try:
        import Rhino.Geometry as rg

        bars = []

        # Define hook geometry parameters
        r = centerline_bend_radius
        ext = hook_extension_length
        elev = bar_elevation
        # The straight part of the bar is the span
        span = span_length_in

        # Define vectors for plane construction
        X_AXIS = rg.Vector3d(1, 0, 0)
        Y_AXIS = rg.Vector3d(0, 1, 0)
        Z_AXIS = rg.Vector3d(0, 0, 1)

        for i in range(num_bars):
            y = i * a_bar_spacing

            r   = centerline_bend_radius
            ext = hook_extension_length
            z   = bar_elevation
            L   = span_length_in

            curves = []

            # 1) Left extension (line)
            curves.append(rg.LineCurve(rg.Point3d(ext, y, z + 2*r), rg.Point3d(0.0, y, z + 2*r)))

            # 2) Left top arc (top-LEFT quadrant)
            # Center at (r, y, z+r), shift right by r from the left end
            cen_lt = rg.Point3d(r, y, z + r)
            pl_lt = rg.Plane(cen_lt, rg.Vector3d(-1, 0, 0), rg.Vector3d(0, 0, 1))
            arc_lt = rg.Arc(pl_lt, r, math.pi/2.0)
            curves.append(arc_lt.ToNurbsCurve())

            # 3) Left vertical leg (line)
            curves.append(rg.LineCurve(rg.Point3d(r, y, z + r), rg.Point3d(r, y, z)))

            # 4) Left bottom arc (bottom-LEFT quadrant)
            # Center at (r, y, z + r), shift right by r and up by r from origin
            cen_lb = rg.Point3d(r, y, z + r)
            pl_lb = rg.Plane(cen_lb, rg.Vector3d(-1, 0, 0), rg.Vector3d(0, 0, -1))
            arc_lb = rg.Arc(pl_lb, r, math.pi/2.0)
            curves.append(arc_lb.ToNurbsCurve())

            # 5) Bottom straight (line)
            curves.append(rg.LineCurve(rg.Point3d(r, y, z), rg.Point3d(L - r, y, z)))

            # 6) Right bottom arc (bottom-RIGHT quadrant)
            # Center at (L - r, y, z + r), shift left by r and up by r from right end
            cen_rb = rg.Point3d(L - r, y, z + r)
            pl_rb = rg.Plane(cen_rb, rg.Vector3d(1, 0, 0), rg.Vector3d(0, 0, -1))
            arc_rb = rg.Arc(pl_rb, r, math.pi/2.0)
            curves.append(arc_rb.ToNurbsCurve())

            # 7) Right vertical leg (line)
            curves.append(rg.LineCurve(rg.Point3d(L - r, y, z + r), rg.Point3d(L - r, y, z)))

            # 8) Right top arc (top-RIGHT quadrant)
            # Center at (L - r, y, z + r), shift left by r
            cen_rt = rg.Point3d(L - r, y, z + r)
            pl_rt = rg.Plane(cen_rt, rg.Vector3d(1, 0, 0), rg.Vector3d(0, 0, 1))
            arc_rt = rg.Arc(pl_rt, r, math.pi/2.0)
            curves.append(arc_rt.ToNurbsCurve())

            # 1) Left extension (line)
            curves.insert(0, rg.LineCurve(rg.Point3d(ext, y, z + 2*r), rg.Point3d(r, y, z + 2*r)))

            # 9) Right extension (line)
            curves.append(rg.LineCurve(rg.Point3d(L - r, y, z + 2*r), rg.Point3d(L - ext, y, z + 2*r)))

            # Join all curves into a single polycurve
            centerline_curve = rg.PolyCurve()
            for curve in curves:
                if curve and curve.IsValid:
                    centerline_curve.Append(curve)

            # Return individual curves (Grasshopper will display them)
            bars.extend(curves)

        return bars

    except ImportError:
        # Not in Rhino environment - return None
        return None
    except Exception as e:
        print(f"Error in generate_a_bars: {e}")
        import traceback
        print(traceback.format_exc())
        return None


if __name__ == '__main__':
    # Auto-detect if running in Grasshopper or PyCharm
    # In Grasshopper, input variables are automatically created from component inputs
    # In PyCharm, we'll use default values for testing

    # Set defaults for PyCharm/testing
    if 'span_length' not in dir():
        span_length = 20
    if 'continuous_span' not in dir():
        continuous_span = False
    if 'over_side_drainage' not in dir():
        over_side_drainage = True
    if 'deck_width' not in dir():
        deck_width = 24.0  # Default bridge width in feet
    if 'output_json' not in dir():
        output_json = False

    try:
        import json

        params = get_deck_parameters(span_length, continuous_span, over_side_drainage)

        # Basic deck properties (simple values)
        thickness = params['thickness']
        # Use the general top cover from params
        top_cover = 2.5
        bot_cover = 1.5

        # Generate A-bar geometry
        a_bars = generate_a_bars(
            span_length=span_length,
            a_bar_size=params['a_bar_size'],
            a_bar_spacing=params['a_bar_spacing'],
            deck_thickness=thickness,
            deck_width=deck_width,
            bot_cover=bot_cover,
            top_cover=top_cover
        )

        # Rebar details - main deck bars (A/B/M/N) and edge bars (C/D/E and edge dimensions)
        rebar_details = {
            'a_bar': {'size': params['a_bar_size'], 'spacing': params['a_bar_spacing']},
            'b_bar': {'size': params['b_bar_size'], 'spacing': params['b_bar_spacing']},
            'm_bar': {'size': params['m_bar_size'], 'spacing': params['m_bar_spacing']},
            'n_bar': {'size': params['n_bar_size'], 'spacing': params['n_bar_spacing']},
            'c_bar': {'size': params.get('c_bar_size', 0), 'spacing': params.get('c_bar_spacing', 0), 'length': params.get('c_bar_length', 0)},
            'd_bar': {'size': params.get('d_bar_size', 0), 'spacing': params.get('d_bar_spacing', 0), 'length': params.get('d_bar_length', 0)},
            'e_bar': {'size': params.get('e_bar_size', 0), 'spacing': params.get('e_bar_spacing', 0), 'length': params.get('e_bar_length', 0)},
            'edge_d': params.get('edge_d', 0),
            'edge_x': params.get('edge_x', 0),
            'd_bar_num': params.get('d_bar_num', 0),
            'e_bar_num': params.get('e_bar_num', 0),
            'f_bar': {'size': params.get('f_bar_size', 0), 'no': params.get('f_bar_no', 0), 'length': params.get('f_bar_length', 0)},
            'g_bar': {'size': params.get('g_bar_size', 0), 'no': params.get('g_bar_no', 0), 'length': params.get('g_bar_length', 0)},
            'h_bar': {'size': params.get('h_bar_size', 0), 'no': params.get('h_bar_no', 0), 'length': params.get('h_bar_length', 0)},
            'j_bar': {'size': params.get('j_bar_size', 0), 'no': params.get('j_bar_no', 0), 'length': params.get('j_bar_length', 0)},
            'k_bar': {'size': params.get('k_bar_size', 0), 'no': params.get('k_bar_no', 0), 'length': params.get('k_bar_length', 0)},
        }

        # Convert to JSON string for Grasshopper
        rebar_details = json.dumps(rebar_details)

        # Continuous span specific variables
        continuous_variables = {
            'a_bar_a': params.get('a_bar_a', 0),
            'a_bar_length': params.get('a_bar_length', 0),
            'b_bar_length': params.get('b_bar_length', 0),
            'm_bar_no': params.get('m_bar_no', 0),
            'n_bar_no': params.get('n_bar_no', 0),
            'f_bar_f': params.get('f_bar_f', 0),
            'u_bar_lap': params.get('u_bar_lap', 0),
        }

        # Convert to JSON string for Grasshopper
        continuous_variables = json.dumps(continuous_variables)

        # Full params as JSON string for advanced users
        all_parameters = json.dumps(params)

        # Status message
        if output_json:
            out = all_parameters
            print(out)
        else:
            print_parameters(params)
            out = f"Bridge Deck Parameters - {params['bridge_type'].upper()} SPAN - {params['edge_type'].replace('_', ' ').title()}"

    except ValueError as e:
        error_msg = f"Error: {e}"
        print(error_msg, file=sys.stderr)
        out = error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        print(error_msg, file=sys.stderr)
        import traceback
        print(traceback.format_exc())
        out = error_msg
