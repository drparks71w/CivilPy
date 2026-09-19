"""Run in Rhino 8 to refine the repository-generated box bridge gallery."""
import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'civilpy_box_slabs', root/'src'/'civilpy'/'structural'/'rhino_box_slabs.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if __name__ == '__main__':
    import Rhino
    doc = globals().get('__rhino_doc__') or Rhino.RhinoDoc.ActiveDoc
    module.refine(doc, root/'Notebooks'/'output'/'box_bridge_details')
