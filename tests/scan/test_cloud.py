#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""PointCloud container, voxel accumulator, and file round-trips."""

import numpy as np
import pytest

from civilpy.scan import cloud as C


def test_pointcloud_validation_and_basics():
    with pytest.raises(ValueError):
        C.PointCloud(np.zeros((3, 2)))
    with pytest.raises(ValueError):
        C.PointCloud(np.zeros((3, 3)), intensity=np.zeros(2))
    pc = C.PointCloud(np.arange(9.0).reshape(3, 3), intensity=[1, 2, 3])
    assert len(pc) == 3
    assert "3 points" in repr(pc)
    lo, hi = pc.bounds
    assert lo.tolist() == [0, 1, 2] and hi.tolist() == [6, 7, 8]
    sub = pc.select([0, 2])
    assert len(sub) == 2 and sub.intensity.tolist() == [1, 3]
    empty = C.PointCloud(np.zeros((0, 3)))
    assert empty.bounds[0].tolist() == [0, 0, 0]
    assert len(empty.to_local()) == 0


def test_local_world_round_trip():
    world = np.array([[1.5e6 + 0.25, 4e5 + 0.5, 700.75], [1.5e6 + 3, 4e5 + 3, 703]])
    pc = C.PointCloud(world).to_local()
    assert pc.origin.tolist() == [1.5e6, 4e5, 700.0]
    assert pc.xyz[0].tolist() == pytest.approx([0.25, 0.5, 0.75])
    again = pc.to_local()                        # idempotent re-base
    assert np.allclose(again.world_xyz, world)
    assert np.allclose(pc.to_world().xyz, world)
    assert np.allclose(pc.to_local(origin=(1, 1, 1)).world_xyz, world)
    assert pc.with_normals(np.tile([0, 0, 1.0], (2, 1))).normals.shape == (2, 3)


def test_concat_keeps_common_attributes():
    a = C.PointCloud(np.zeros((2, 3)), intensity=[1, 2], origin=(10, 0, 0))
    b = C.PointCloud(np.ones((1, 3)), intensity=[3], rgb=[[1, 2, 3]], origin=(0, 0, 0))
    m = C.PointCloud.concat([a, b])
    assert len(m) == 3
    assert m.intensity.tolist() == [1, 2, 3]
    assert m.rgb is None                         # a lacks rgb
    assert np.allclose(m.xyz[2], [-9, 1, 1])     # re-based on the first origin
    assert len(C.PointCloud.concat([])) == 0


def test_voxel_accumulator_averages_per_voxel():
    acc = C.VoxelAccumulator(1.0)
    acc.add(np.array([[0.2, 0.2, 0.2], [0.8, 0.8, 0.8], [2.5, 2.5, 2.5]]),
            intensity=[10, 20, 30], rgb=[[0, 0, 0], [2, 2, 2], [4, 4, 4]], classification=[2, 3, 6])
    acc.add(np.array([[2.7, 2.7, 2.7]]), intensity=[50], rgb=[[6, 6, 6]], classification=[1])
    acc.add(np.zeros((0, 3)))
    assert len(acc) == 2 and acc.n_points == 4
    out = acc.result()
    order = np.argsort(out.xyz[:, 0])
    assert np.allclose(out.xyz[order[0]], [0.5, 0.5, 0.5])
    assert np.allclose(out.xyz[order[1]], [2.6, 2.6, 2.6])
    assert out.intensity[order].tolist() == [15, 40]
    assert out.rgb[order].tolist() == [[1, 1, 1], [5, 5, 5]]
    assert out.classification[order].tolist() == [2, 6]        # first seen wins
    with pytest.raises(ValueError):
        C.VoxelAccumulator(0)
    with pytest.raises(ValueError):
        C.VoxelAccumulator(1.0, anchor=(5e6, 5, 5)).add(np.zeros((1, 3)))
    below = C.VoxelAccumulator(1.0, anchor=(5, 5, 5))          # anchor above the data is fine
    below.add(np.zeros((1, 3)))
    assert len(below) == 1


def test_chunk_reducer_options():
    xyz = np.column_stack([np.arange(100.0), np.zeros(100), np.arange(100.0)])
    r = C._ChunkReducer(bbox=(10, -1, 49, 1), zrange=(0, 30), every=2)
    r.add(xyz[:50])
    r.add(xyz[50:])
    out = r.result()
    assert (out.xyz[:, 0] >= 10).all() and (out.xyz[:, 2] <= 30).all()
    assert len(out) == 11                                       # 10..30 step 2
    r = C._ChunkReducer(max_points=7)
    r.add(xyz[:5])
    r.add(xyz[5:])
    r.add(xyz[5:])                                              # ignored once full
    assert r.done() and len(r.result()) == 7
    r = C._ChunkReducer(classes=[2])
    r.add(xyz, classification=np.array([2] * 10 + [0] * 90))
    assert len(r.result()) == 10
    assert len(C._ChunkReducer().result()) == 0
    r = C._ChunkReducer(voxel=10.0)
    r.add(xyz)
    assert len(r.result()) == 10
    r = C._ChunkReducer(bbox=(1000, 1000, 1001, 1001))
    r.add(xyz)
    assert len(r.result()) == 0


def test_ply_round_trip(tmp_path, rng):
    xyz = rng.uniform(0, 10, (50, 3))
    pc = C.PointCloud(xyz, rgb=rng.integers(0, 65535, (50, 3)), normals=np.tile([0, 0, 1.0], (50, 1)),
                      intensity=rng.uniform(0, 100, 50), origin=(100, 200, 300))
    for binary in (True, False):
        p = C.write_ply(pc, tmp_path / f"a_{binary}.ply", binary=binary)
        back = C.read_ply(p)
        assert np.allclose(back.xyz, xyz, atol=1e-4)
        assert back.rgb.max() <= 255 and back.normals is not None and back.intensity is not None
    p = C.write_ply(pc, tmp_path / "w.ply", world=True)
    back = C.read_ply(p, local=True)
    assert np.allclose(back.world_xyz, xyz + [100, 200, 300])
    unit = C.PointCloud(xyz, rgb=np.full((50, 3), 0.5))
    assert C.read_ply(C.write_ply(unit, tmp_path / "u.ply")).rgb.max() == pytest.approx(128, abs=1)
    assert pc.save(tmp_path / "s.ply").exists()
    with pytest.raises(ValueError):
        pc.save(tmp_path / "s.pod")
    (tmp_path / "bad.ply").write_text("nope\n")
    with pytest.raises(ValueError):
        C.read_ply(tmp_path / "bad.ply")
    (tmp_path / "bad2.ply").write_text("ply\nformat ascii 1.0\n")
    with pytest.raises(ValueError):
        C.read_ply(tmp_path / "bad2.ply")


def test_xyz_round_trip(tmp_path, rng):
    xyz = rng.uniform(0, 10, (40, 3)) + [1e6, 2e5, 500]
    pc = C.PointCloud(xyz, rgb=rng.integers(0, 255, (40, 3)), intensity=rng.integers(0, 100, 40))
    p = C.write_xyz(pc, tmp_path / "a.xyz")
    back = C.read_xyz(p)
    assert np.allclose(back.world_xyz, xyz, atol=1e-3)
    assert back.rgb.shape == (40, 3) and back.intensity is not None
    only = C.read_xyz(C.write_xyz(C.PointCloud(xyz), tmp_path / "b.txt"), local=False)
    assert np.allclose(only.xyz, xyz, atol=1e-3)
    four = C.PointCloud(xyz, intensity=np.arange(40.0))
    assert C.read_xyz(C.write_xyz(four, tmp_path / "c.xyz")).intensity is not None
    csv = C.read_xyz(C.write_xyz(pc, tmp_path / "d.csv", delimiter=","))
    assert len(csv) == 40
    small = C.read_xyz(p, chunk_size=7, voxel=5.0)              # chunked + voxel path
    assert 0 < len(small) < 40
    seen = []
    C.read_xyz(p, columns={"x": 0, "y": 1, "z": 2}, progress=lambda a, b: seen.append(a))
    assert seen
    assert C.read_cloud(p).source == str(p)
    assert len(C.read_xyz(p, bbox=(0, 0, 1, 1))) == 0
    with pytest.raises(ValueError):
        C.read_cloud(tmp_path / "x.pod")
    with pytest.raises(ValueError):
        C.read_cloud(tmp_path / "x.foo")


laspy = pytest.importorskip("laspy")


def test_las_round_trip(tmp_path, rng):
    xyz = rng.uniform(0, 100, (500, 3)) + [1.5e6, 4e5, 700]
    pc = C.PointCloud(xyz, intensity=rng.integers(0, 65535, 500),
                      rgb=rng.integers(0, 255, (500, 3)), classification=np.full(500, 2, np.uint8))
    p = C.write_las(pc, tmp_path / "a.las")
    info = C.las_info(p)
    assert info["point_count"] == 500 and info["has_rgb"] and info["point_format"] == 2
    back = C.read_las(p)
    assert np.allclose(back.world_xyz, xyz, atol=2e-3)
    assert back.classification.tolist() == [2] * 500 and back.rgb.max() > 255
    clipped = C.read_las(p, bbox=(1.5e6, 4e5, 1.5e6 + 50, 4e5 + 50), local=False)
    assert 0 < len(clipped) < 500 and (clipped.xyz[:, 0] <= 1.5e6 + 50).all()
    vox = C.read_las(p, voxel=25.0, chunk_size=100)
    assert 0 < len(vox) <= 64
    capped = C.read_las(p, max_points=10, chunk_size=100, progress=lambda a, b: None)
    assert len(capped) == 10
    assert len(C.read_las(p, classes=[6])) == 0
    assert C.read_cloud(p).source == str(p)
    assert pc.save(tmp_path / "b.las").exists()
    unit_rgb = C.PointCloud(xyz, rgb=np.full((500, 3), 0.5))
    assert C.read_las(C.write_las(unit_rgb, tmp_path / "c.las")).rgb.max() > 30000
    no_rgb = C.write_las(C.PointCloud(xyz, rgb=np.zeros((500, 3))), tmp_path / "d.las", point_format=0)
    assert C.read_las(no_rgb).rgb is None
