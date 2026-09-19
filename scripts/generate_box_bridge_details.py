"""Repository convenience wrapper for the packaged box bridge generator."""
from pathlib import Path
from civilpy.structural.box_bridge_gallery import generate

if __name__ == '__main__':
    generate(Path(__file__).resolve().parents[1]/'Notebooks'/'output'/'box_bridge_details')
