# Validation Testing: Bridge Multi-Representation Contract (A3)

## Objective
The objective of Milestone A3 is to establish a "hub-and-spoke" contract where bridge objects are defined by their engineering parameters and placement (Station/Offset on an Alignment), and can emit both:
1. **Geometric Representation** (for a Common Data Environment like Rhino/Grasshopper).
2. **Analytical Representation** (a `StructuralModel` for FEA solvers like MIDAS Civil).

## Intended Utilization

### 1. Site Setup
Reviewers should start with an `Alignment` and optionally a `Terrain` object.
```python
from civilpy.transportation.alignment import Alignment, Tangent
from civilpy.transportation.terrain import Terrain

# Create a simple alignment
align = Alignment(start_point=(0,0), start_bearing_deg=90, 
                  elements=[Tangent(length_ft=500)])
```

### 2. Component Placement
Bridge components (like Girders, Abutments, or Slabs) are instantiated with a `Placement` object.
```python
from civilpy.structural.placement import Placement

# Place a component at Station 1+00, 12ft Right
p = Placement(alignment=align, station=100.0, offset=12.0)
print(f"Global coordinates: {p.point}")
```

### 3. Multi-Representation Extraction
Every `BridgeComponent` must implement the `geometry()` and `structural_model()` methods.

#### Rhino/CDE Spoke
*   **Method**: `component.geometry()`
*   **Output**: A data structure (dictionary or list of primitives) containing points, lines, or BREPs.
*   **Validation**: In Grasshopper, these primitives are tagged with UserText (e.g., `gdr.ID`, `gdr.Section`) which the `civilpy` Rhino reader uses to rebuild the model.

#### MIDAS/Analysis Spoke
*   **Method**: `component.structural_model()`
*   **Output**: A `civilpy.structural.structural_model.StructuralModel` object.
*   **Validation**: This hub object can be pushed directly to MIDAS via:
    ```python
    from civilpy.structural.midas_models import push_midas
    model = component.structural_model()
    push_midas(model)
    ```

## Verification Checklist for Reviewers
- [ ] **Placement Accuracy**: Ensure `p.point` matches the expected 3D coordinate calculated from the alignment.
- [ ] **Geometry Tags**: Verify that the geometry output contains the required tags for the MIDAS pipeline.
- [ ] **Model Connectivity**: Verify that the `StructuralModel` produced by a component has nodes and elements that correctly represent the engineering intent.
