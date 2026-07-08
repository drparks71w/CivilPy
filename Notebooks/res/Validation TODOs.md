Check concrete_slab_ghpython.py and odot_bridge_generator_ghpython.py 
to verify that they're still needed with the updated workflow. 

# General Gripes 

These are # //TODOs that are true for basically every SCD that's been built so far:

- Orientation is incorrect. Top views usually come through, but "Right" and "Front" are generally swapped
- Objects take in basic native types always, not the correct "Types" that I would expect from a design stand point, 
terrain, centerline, elevation, coordinates, reference line, etc. 
  - Basically all objects in a bridge are going to be based on their location (station+offset) along the bridge CL or 
  centerline of construction
  - Certain objects will be referenced with regard to the beam centerline, which the beam will reference the station+\
  offset, other objects, like parapet/guardrail will be a "template" pushed along an alignment offset along the bridge
- All generated objects should have user-text attributes that tie back to their CDE/IFC/Midas counterpart (if one exists)
- Layer names should be human readable and hierarchical, not encoded: I.E. rather than an object being output to Deck -> 
AS-1-15, have it output as Deck->Approach Slab->Rebar. For quantity calculation purposes, rebar should have attributes 
like diameter so that BIM functions can be performed, clash detection, quantity take-offs, etc. Similarly, use the 
"material" feature within Rhino to get realistic depictions for materials like steel, concrete, asphalt, etc. If an ODOT
pay item exists for a material, include the pay-item as a user-text attribute so that cost estimates can be generated.
- All objects should have a preview of some kind in the grasshopper menu, preferably both the internal shell in addition 
to "hidden" internal components like rebar.
- Objects that output "reference" lines, like "Girder Centerline" that tools like midas will rely on should output that 
linework typed as the appropriate type of line
- When inputs have very limited numbers of string options as inputs, design them for use with a drop down.
- Missing 3 Expansion Joint Standards - EXJ-2-81, EXJ-3-82, EXJ-6-17
- 

| Status |   SCD Name/Notes    | Quality Score |
|:-------|:-------------------:|:-------------:|
| ✅     |  A-1-20 - Reviewed  |     2/10      |
| ✅     | AS-1-15 - Reviewed  |     7/10      |
| ✅     | AS-2-15 - Reviewed  |     5/10      |
| ✅     |   BCHW - Reviewed   |     2/10      |
| ✅     | BD-1-11 - Reviewed  |     4/10      |
| ✅     | CPA-1-08 - Reviewed |     5/10      |
| ✅     | CPP-1-08 - Reviewed |     5/10      |
| ✅     | CS-1-24 - Reviewed  |     4/10      |
| ✅     | DS-1-92 - Reviewed  |     8/10      |
| ✅     | EXJ-4-87 - Reviewed |     4/10      |
| ✅     | EXJ-5-93 - Reviewed |     4/10      |

