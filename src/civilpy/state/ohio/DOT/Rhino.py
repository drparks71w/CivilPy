import plotly.graph_objects as go
import numpy as np

import rhinoinside

rhinoinside.load()

import Rhino.Geometry as rg


def display_brep(brep, color='lightblue', opacity=1.0):
    """
    Converts a Rhino BREP into a mesh and displays it interactively using Plotly.
    """
    # 1. Convert your Rhino BREP to a Mesh
    mesh_params = rg.MeshingParameters.Default
    rhino_meshes = rg.Mesh.CreateFromBrep(brep, mesh_params)

    final_rhino_mesh = rg.Mesh()
    for m in rhino_meshes:
        final_rhino_mesh.Append(m)

    # Plotly only likes triangles, so we force Rhino to triangulate everything
    final_rhino_mesh.Faces.ConvertQuadsToTriangles()

    # 2. Extract Data for Plotly
    verts = np.array([[v.X, v.Y, v.Z] for v in final_rhino_mesh.Vertices])

    # Extract triangle indices
    I = [f.A for f in final_rhino_mesh.Faces]
    J = [f.B for f in final_rhino_mesh.Faces]
    K = [f.C for f in final_rhino_mesh.Faces]

    # 3. Create the Plotly 3D Figure
    fig = go.Figure(data=[
        go.Mesh3d(
            x=verts[:, 0], y=verts[:, 1], z=verts[:, 2],
            i=I, j=J, k=K,
            color=color,
            opacity=opacity,
            flatshading=True # Gives it a clean, CAD-like appearance
        )
    ])

    # Force a 1:1:1 aspect ratio so your geometry doesn't look stretched
    fig.update_layout(
        scene=dict(aspectmode='data'),
        margin=dict(l=0, r=0, b=0, t=0) # Removes excess white space
    )

    # 4. Display it (No server required!)
    fig.show()