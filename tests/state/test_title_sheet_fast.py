"""Fast title-sheet detection path (detect_sections / render_region /
input-size cap).  Uses a fake model — the real weights are 159 MB and
live outside version control."""
import pytest

torch = pytest.importorskip("torch")
fitz = pytest.importorskip("fitz")

from PIL import Image

from civilpy.state.ohio.DOT import title_sheet as ts


class FakeModel:
    """Returns one 'PID' box at a fixed fractional position of whatever
    image it receives, plus a low-score 'Sheet Index' box."""

    def __init__(self):
        self.seen_sizes = []

    def __call__(self, batch):
        c, h, w = batch[0].shape
        self.seen_sizes.append((w, h))
        pid_id = ts.DISCOVERED_LABELS.index("PID") + 1
        si_id = ts.DISCOVERED_LABELS.index("Sheet Index") + 1
        return [{
            "scores": torch.tensor([0.9, 0.2]),
            "labels": torch.tensor([pid_id, si_id]),
            "boxes": torch.tensor([
                [0.1 * w, 0.1 * h, 0.5 * w, 0.5 * h],
                [0.6 * w, 0.6 * h, 0.9 * w, 0.9 * h]]),
        }]

    def eval(self):
        return self


@pytest.fixture(scope="module")
def sheet_pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("ts") / "sheet.pdf"
    doc = fitz.open()
    doc.new_page(width=2448, height=1584)      # 34x22in ODOT sheet
    doc.save(path)
    return str(path)


class TestDetectSections:
    def test_single_pass_all_labels(self, sheet_pdf):
        model = FakeModel()
        out = ts.detect_sections(model, sheet_pdf, score_thresh=0.5)
        assert len(model.seen_sizes) == 1          # ONE inference
        assert list(out) == ["PID"]                # 0.2 box filtered

    def test_renders_at_model_native_size(self, sheet_pdf):
        model = FakeModel()
        ts.detect_sections(model, sheet_pdf)
        w, h = model.seen_sizes[0]
        assert max(w, h) == ts.DETECT_LONG_SIDE

    def test_box_pdf_in_page_points(self, sheet_pdf):
        out = ts.detect_sections(FakeModel(), sheet_pdf)
        x0, y0, x1, y1 = out["PID"]["box_pdf"]
        assert x0 == pytest.approx(0.1 * 2448, rel=1e-3)
        assert y1 == pytest.approx(0.5 * 1584, rel=1e-3)
        assert out["PID"]["page_dimensions"] == (2448.0, 1584.0)

    def test_threshold_configurable(self, sheet_pdf):
        out = ts.detect_sections(FakeModel(), sheet_pdf, score_thresh=0.1)
        assert set(out) == {"PID", "Sheet Index"}


class TestRenderRegion:
    def test_clip_render_size(self, sheet_pdf):
        img = ts.render_region(sheet_pdf, 1, (100, 100, 400, 300),
                               dpi=300, pad_pts=0)
        # 300 pts x 200 pts at 300 dpi -> ~1250 x ~833 px
        assert img.size[0] == pytest.approx(300 / 72 * 300, abs=3)
        assert img.size[1] == pytest.approx(200 / 72 * 300, abs=3)

    def test_clip_clamped_to_page(self, sheet_pdf):
        img = ts.render_region(sheet_pdf, 1, (-50, -50, 100, 100), dpi=72)
        assert img.size[0] <= 2448 and img.size[1] <= 1584


class TestInputSizeCap:
    def test_huge_image_downscaled_boxes_upscaled(self):
        model = FakeModel()
        big = Image.new("RGB", (4000, 2600), "white")
        info = ts.find_section_in_image(model, big, "PID")
        w, h = model.seen_sizes[0]
        assert max(w, h) == ts.DETECT_LONG_SIDE    # inference downscaled
        # ...but the returned box is in ORIGINAL image coordinates
        assert info["best_box"][0] == pytest.approx(0.1 * 4000, rel=0.01)
        assert info["best_box"][3] == pytest.approx(0.5 * 2600, rel=0.01)
        assert info["original_image"].size == (4000, 2600)

    def test_small_image_untouched(self):
        model = FakeModel()
        small = Image.new("RGB", (800, 600), "white")
        info = ts.find_section_in_image(model, small, "PID")
        assert model.seen_sizes[0] == (800, 600)
        assert info["best_box"][2] == pytest.approx(0.5 * 800, rel=0.01)
