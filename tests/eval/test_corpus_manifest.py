"""D3a corpus v0: the manifest, the annotations, the holdout rule and the fetch helpers.

Expected values are hand-computed in the comments beside each assertion; none comes from running
QREP. Record fragments and dimension strings are hand-written in the shapes the museum records
use; no saved third-party page is used. Every check that reads corpus/ reads the committed
files, so a row, an image or an annotation that breaks a rule fails here before corpus-guard runs.
"""

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

import corpus_fetch as cf
from qrep.contract import OuterEdgeFrame, ReadRequest
from qrep_eval import annotation as an

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "corpus"
MANIFEST = CORPUS / "manifest.csv"
ANNOTATIONS = sorted((CORPUS / "annotations").glob("*.json"))
IMAGES = sorted(p for p in (CORPUS / "images").glob("*") if p.name != ".gitkeep")


def rows() -> list[dict[str, str]]:
    return cf.read_manifest(MANIFEST)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------------------------
# Manifest columns and vocabularies
# ---------------------------------------------------------------------------------------------


def test_manifest_has_the_required_columns_in_order():
    # Source: plan D3a, criterion 4: file and license (corpus-guard), then the listed columns.
    header = MANIFEST.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == [
        "file", "license", "source", "object_id", "title", "landing_url", "image_url",
        "rights_flag", "policy_url", "credit", "dimensions_text", "finished_in", "sha256",
        "file_sha256", "px_w", "px_h", "tier", "class", "capture", "commit_ok",
    ]
    assert tuple(header) == cf.COLUMNS


def test_every_row_licenses_by_its_source_flag():
    # Source: plan D3a, criterion 2: CC0-1.0 where the institution dedicates the image CC0
    # (Met, Smithsonian), PDM-1.0 where it marks the work public domain (AIC, LACMA).
    expected = {"met": "CC0-1.0", "smithsonian": "CC0-1.0", "aic": "PDM-1.0", "lacma": "PDM-1.0"}
    for row in rows():
        assert row["source"] in expected, row["file"]
        assert row["license"] == expected[row["source"]], row["file"]
        assert row["rights_flag"] == cf.SOURCES[row["source"]].rights_flag, row["file"]
        assert row["policy_url"] == cf.SOURCES[row["source"]].policy_url, row["file"]


def test_every_row_has_hash_formats_and_unique_identity():
    # Source: plan section 5.D rules: sha256 is the source image's hash, 64 lowercase hex, and
    # file_sha256 is empty or the committed copy's own 64-hex hash.
    seen_files, seen_sha = set(), set()
    for row in rows():
        assert len(row["sha256"]) == 64 and set(row["sha256"]) <= set("0123456789abcdef")
        assert row["file_sha256"] == "" or (
            len(row["file_sha256"]) == 64 and set(row["file_sha256"]) <= set("0123456789abcdef")
        )
        assert row["file"] not in seen_files and row["sha256"] not in seen_sha, row["file"]
        seen_files.add(row["file"])
        seen_sha.add(row["sha256"])


def test_every_row_uses_the_tier_class_capture_and_commit_vocabularies():
    # Source: plan D3a, criterion 5: tiers A, B, R (with a refusal class) and X; captures from
    # section 8.2; museum photos are museum scans.
    for row in rows():
        tier, klass = row["tier"], row["class"]
        assert tier in cf.TIERS, row["file"]
        assert klass in cf.CLASSES_BY_TIER[tier], (row["file"], tier, klass)
        assert row["capture"] == "museum_scan", row["file"]
        assert row["commit_ok"] in {"yes", "no"}, row["file"]
        assert int(row["px_w"]) > 0 and int(row["px_h"]) > 0, row["file"]
        assert row["title"] and row["object_id"] and row["credit"], row["file"]


def test_every_row_points_only_at_allowlisted_hosts():
    # Source: plan D3a, criterion 1: fetch only from the allowlisted open-access sources.
    for row in rows():
        for column in ("landing_url", "image_url", "policy_url"):
            cf.check_host(row[column])


def test_finished_sizes_keep_their_source_text_and_read_approximate():
    # Source: plan D3a, criterion 4: parse finished sizes, keep the source text, mark approximate.
    for row in rows():
        if row["finished_in"]:
            assert row["finished_in"].startswith("~"), row["file"]
            assert row["dimensions_text"], row["file"]
            parsed = cf.parse_finished_size(row["dimensions_text"])
            assert parsed is not None and cf.format_finished(*parsed) == row["finished_in"]


def test_uncommitted_rows_name_their_cache_path():
    # Every fetched image lives in the main checkout's corpus/private/cache/; a row that licenses
    # no committed file names that path relative to corpus/, so annotations can name it.
    for row in rows():
        if not row["file"].startswith("images/"):
            assert row["file"] == "private/cache/" + cf.cache_name(row["source"], row["object_id"])
            assert row["file_sha256"] == ""


# ---------------------------------------------------------------------------------------------
# Committed images
# ---------------------------------------------------------------------------------------------


def test_committed_images_are_few_small_licensed_and_bound_to_their_rows():
    # Source: plan D3a, criterion 10: at most 10 images, each at most 800 px, each with a row
    # whose file_sha256 is the committed copy's hash (the copy is downsized, so it differs from
    # the source's sha256).
    by_file = {row["file"]: row for row in rows()}
    assert 1 <= len(IMAGES) <= 10
    for path in IMAGES:
        row = by_file["images/" + path.name]
        assert row["commit_ok"] == "yes" and row["tier"] in {"A", "B", "R"}
        assert row["file_sha256"] == sha256_file(path)
        assert row["file_sha256"] != row["sha256"]
        with Image.open(path) as image:
            assert max(image.size) <= 800
    committed_rows = [r for r in rows() if r["file"].startswith("images/")]
    assert sorted(r["file"] for r in committed_rows) == sorted("images/" + p.name for p in IMAGES)


# ---------------------------------------------------------------------------------------------
# The eval set
# ---------------------------------------------------------------------------------------------


def eval_set() -> dict[str, list[dict[str, str]]]:
    """The v0 eval set: the manifest rows that carry an annotation, by tier. The manifest keeps
    every screened photo; the eval set is the annotated subset (corpus/README.md)."""
    annotated = {an.load(path).photo for path in ANNOTATIONS}
    chosen: dict[str, list[dict[str, str]]] = {}
    for row in rows():
        if row["file"] in annotated:
            chosen.setdefault(row["tier"], []).append(row)
    return chosen


def test_the_v0_eval_set_holds_every_tier_a_photo_and_at_least_30_refusals():
    # Source: plan D3a, criterion 6: every tier A photo found, and at least 30 refusal photos
    # (G4 needs n of at least 30).
    chosen = eval_set()
    tier_a = [row["file"] for row in rows() if row["tier"] == "A"]
    assert tier_a and sorted(r["file"] for r in chosen.get("A", [])) == sorted(tier_a)
    assert len(chosen.get("R", [])) >= 30
    assert "X" not in chosen


def test_eval_refusals_are_weighted_toward_on_point_look_alikes():
    # Source: plan D3a, criterion 6: the eval set's refusals are weighted toward on-point squares
    # and triangle quilts, so on_point is their largest class.
    refusals = [row["class"] for row in eval_set().get("R", [])]
    counts = {klass: refusals.count(klass) for klass in set(refusals)}
    assert max(counts, key=counts.get) == "on_point"


# ---------------------------------------------------------------------------------------------
# Holdout rule
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        # int("0000000c", 16) = 12; 12 % 3 = 0, so holdout.
        ("0000000c", True),
        # int("0000000d", 16) = 13; 13 % 3 = 1, so dev.
        ("0000000d", False),
        # int("ffffffff", 16) = 4294967295 = 3 x 1431655765, so holdout.
        ("ffffffff", True),
        # int("00000001", 16) = 1; 1 % 3 = 1, so dev.
        ("00000001", False),
        # int("0000000f", 16) = 15; 15 % 3 = 0, so holdout.
        ("0000000f", True),
    ],
)
def test_holdout_rule_reads_the_first_8_hex_digits(prefix, expected):
    # Source: plan D3a, criterion 9 (the rule corpus/README.md fixes).
    assert an.in_holdout(prefix + "a" * 56) is expected


@pytest.mark.parametrize("bad", ["A" * 64, "0" * 63, "g" * 64, ""])
def test_holdout_rule_refuses_a_malformed_hash(bad):
    with pytest.raises(ValueError):
        an.in_holdout(bad)


def test_readme_fixes_the_holdout_rule_and_the_source_lists():
    # Source: plan D3a, criteria 3 and 9.
    text = (CORPUS / "README.md").read_text(encoding="utf-8")
    assert "first 8 hex digits" in text and "divisible by 3" in text
    for name in ("Met", "Smithsonian", "Art Institute of Chicago", "LACMA", "Cleveland",
                 "Rijksmuseum", "V&A", "Quilt Index", "International Quilt Museum",
                 "Library of Congress", "Mia", "Wikimedia Commons", "906.1", "906.2", "DEMO_KEY"):
        assert name in text, name


# ---------------------------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------------------------


def test_attribution_is_generated_from_the_manifest():
    # Source: plan D3a, criterion 11.
    expected = cf.attribution_markdown(rows())
    assert (CORPUS / "ATTRIBUTION.md").read_text(encoding="utf-8") == expected


def test_attribution_cites_lacma_with_its_site():
    sample = [dict.fromkeys(cf.COLUMNS, "x") | {
        "source": "lacma", "title": "Quilt", "object_id": "M.1", "credit": "Gift",
        "landing_url": "https://collections.lacma.org/node/1", "file": "private/cache/lacma-m-1.jpg",
        "license": "PDM-1.0", "tier": "A",
    }]
    assert "www.lacma.org" in cf.attribution_markdown(sample)


# ---------------------------------------------------------------------------------------------
# Annotation format
# ---------------------------------------------------------------------------------------------

SHA = "0000000d" + "a" * 56
OUTER = {
    "kind": "outer_edge",
    "corners": {
        "top_left": {"x": 100, "y": 50},
        "top_right": {"x": 900, "y": 60},
        "bottom_right": {"x": 890, "y": 750},
        "bottom_left": {"x": 110, "y": 740},
    },
    "bands": [{"width_squares": 1.0}, {"width_squares": 0.5}],
}
FIELD = {
    "kind": "field",
    "corners": {
        "top_left": {"x": 130, "y": 80},
        "top_right": {"x": 870, "y": 90},
        "bottom_right": {"x": 860, "y": 720},
        "bottom_left": {"x": 140, "y": 710},
    },
}
COUNTS = {"blocks_across": 8, "blocks_down": 6, "squares_per_block_across": 5,
          "squares_per_block_down": 5}


def sample(**changes) -> dict:
    doc = {
        "schema_version": 1,
        "photo": "private/cache/met-1.jpg",
        "sha256": SHA,
        "canvas": [1000, 800],
        "frame": [
            {"value": {"outer_edge": OUTER, "field": FIELD}, "provenance": "verified-jake"},
            {"value": {"outer_edge": OUTER}, "provenance": "proposed-a"},
        ],
        "counts": [
            {"value": COUNTS, "provenance": "verified-jake"},
            {"value": COUNTS | {"blocks_across": 7}, "provenance": "proposed-a"},
        ],
        "construction_class": [{"value": "hst", "provenance": "verified-jake"}],
        "fabrics": [{"value": {"count": 3, "roles": ["background", "star", "border"],
                               "palette_hex": ["#f0e8d0", "#8f3b3b", "#28345e"]},
                     "provenance": "verified-jake"}],
        "finished_size": [{"value": {"width_in": 72.0, "height_in": 80.0, "approximate": True,
                                     "source_text": "80 x 72 in."},
                           "provenance": "source-record"}],
        "capture": [{"value": "museum_scan", "provenance": "source-record"}],
    }
    doc.update(changes)
    return doc


def parse(doc: dict) -> an.Annotation:
    return an.Annotation.model_validate_json(json.dumps(doc))


def test_an_annotation_becomes_the_read_request_its_user_would_send():
    # Source: plan D3a, criterion 7 (the mapping D4a uses). By hand, from sample(): the
    # verified-jake claims win over proposed-a, so the frame is OUTER (two bands, 1.0 and 0.5
    # squares, outside in), the counts are 8 across x 5 and 6 down x 5 (not proposed-a's 7), the
    # crop offset is (0, 0) because coordinates are source pixels, and the fabric count is 3.
    request = an.to_read_request(parse(sample()), "photo.png")
    assert isinstance(request, ReadRequest)
    assert request.frame == OuterEdgeFrame.model_validate_json(json.dumps(OUTER))
    assert [band.width_squares for band in request.frame.bands] == [1.0, 0.5]
    assert (request.crop_offset.x, request.crop_offset.y) == (0.0, 0.0)
    assert (request.counts.blocks_across, request.counts.blocks_down) == (8, 6)
    assert (request.counts.squares_per_block_across, request.counts.squares_per_block_down) == (5, 5)
    assert request.fabric_count == 3
    assert request.token == "photo.png"


def test_the_field_frame_maps_when_its_corners_were_confirmed():
    request = an.to_read_request(parse(sample()), "photo.png", frame="field")
    assert request.frame.kind == "field"
    assert (request.frame.corners.top_left.x, request.frame.corners.top_left.y) == (130.0, 80.0)


def test_a_proposal_stands_in_for_truth_only_when_asked():
    doc = sample(frame=[sample()["frame"][1]], counts=[sample()["counts"][1]], fabrics=[])
    with pytest.raises(ValueError):
        an.to_read_request(parse(doc), "photo.png")
    # By hand: proposed-a counts blocks_across 7, and no fabric claim leaves the count unset.
    request = an.to_read_request(parse(doc), "photo.png", prefer=("proposed-a",))
    assert request.counts.blocks_across == 7 and request.fabric_count is None


def test_the_sidecar_view_matches_the_photoreal_shapes():
    # Source: tests/fixtures/photoreal sidecars (quad spans the border; scripts/
    # photoreal_baseline.py:84 adds 2 x border_pitches to cols). By hand from sample():
    # rows = 6 blocks x 5 = 30; cols = 8 blocks x 5 = 40; border_pitches = 1.0 + 0.5 = 1.5;
    # repeat_cells = [5 down, 5 across]; hst is not plain squares, so non_square.
    view = an.sidecar_view(parse(sample()))
    assert view == {
        "canvas": [1000, 800],
        "quad": [[100.0, 50.0], [900.0, 60.0], [890.0, 750.0], [110.0, 740.0]],
        "grid": {"rows": 30, "cols": 40, "border_pitches": 1.5},
        "repeat_cells": [5, 5],
        "palette_hex": ["#f0e8d0", "#8f3b3b", "#28345e"],
        "character": "non_square",
    }


@pytest.mark.parametrize(
    "change",
    [
        # Two claims with one provenance code in one field.
        {"construction_class": [{"value": "hst", "provenance": "proposed-a"},
                                {"value": "qst", "provenance": "proposed-a"}]},
        # An unknown provenance code.
        {"capture": [{"value": "museum_scan", "provenance": "agent"}]},
        # A corner off the 1000 x 800 canvas (x = 1001).
        {"frame": [{"value": {"outer_edge": OUTER | {"corners": OUTER["corners"] | {
            "top_right": {"x": 1001, "y": 60}}}}, "provenance": "proposed-b"}]},
        # Three roles for a count of two.
        {"fabrics": [{"value": {"count": 2, "roles": ["a", "b", "c"]},
                      "provenance": "proposed-a"}]},
        # A count of true is not an integer (strict, as the contract is).
        {"counts": [{"value": COUNTS | {"blocks_across": True}, "provenance": "proposed-a"}]},
        # An unknown field.
        {"notes": "anything"},
        # A malformed photo hash.
        {"sha256": "ABC"},
    ],
)
def test_the_annotation_model_refuses_malformed_input(change):
    with pytest.raises(ValidationError):
        parse(sample(**change))


def test_the_committed_schema_is_the_models_export():
    # Source: plan D3a, criterion 7: the model exports corpus/schema/annotation.schema.json, which
    # the dev annotate page (C3a) writes against; a drift between them fails here.
    committed = (CORPUS / "schema" / "annotation.schema.json").read_text(encoding="utf-8")
    assert committed == an.schema_text()


# ---------------------------------------------------------------------------------------------
# Committed annotations: valid, licensed (the issue #113 rule) and complete
# ---------------------------------------------------------------------------------------------


def test_the_licensed_photo_rule_refuses_an_annotation_of_a_private_photo():
    # Issue #113's case: a cell model of a private photo with no manifest row must fail.
    private = parse(sample(photo="local-photos/IMG_0001.png"))
    licensed = {"private/cache/met-1.jpg": {"license": "CC0-1.0", "sha256": SHA,
                                            "px_w": "1000", "px_h": "800"}}
    assert an.licensed_photo_problems(private, "IMG_0001", licensed)
    assert an.licensed_photo_problems(parse(sample()), "met-1", licensed) == []
    unlicensed = {k: v | {"license": "CC-BY-4.0"} for k, v in licensed.items()}
    assert an.licensed_photo_problems(parse(sample()), "met-1", unlicensed)
    other_bytes = {k: v | {"sha256": "f" * 64} for k, v in licensed.items()}
    assert an.licensed_photo_problems(parse(sample()), "met-1", other_bytes)
    assert an.licensed_photo_problems(parse(sample()), "met-2", licensed)


def test_every_committed_annotation_names_a_licensed_photo():
    # The issue #113 rule, applied by this test until corpus-guard enforces it: every committed
    # corpus/annotations/*.json names a photo with a CC0-1.0 or PDM-1.0 row whose sha256 and
    # canvas match, under the photo's own stem.
    by_file = {row["file"]: row for row in rows()}
    assert ANNOTATIONS
    for path in ANNOTATIONS:
        problems = an.licensed_photo_problems(an.load(path), path.stem, by_file)
        assert problems == [], (path.name, problems)


def test_tier_a_and_refusal_photos_carry_two_independent_proposals():
    # Source: plan D3a, criterion 8: proposed-a and proposed-b for corners, bands, counts and
    # class on every tier A photo, and the class on every refusal photo of the eval set.
    by_file = {row["file"]: row for row in rows()}
    for path in ANNOTATIONS:
        doc = an.load(path)
        tier = by_file[doc.photo]["tier"]
        needed = ("frame", "counts", "construction_class") if tier == "A" else (
            "construction_class",)
        for name in needed:
            codes = {claim.provenance for claim in getattr(doc, name)}
            assert {"proposed-a", "proposed-b"} <= codes, (path.name, name)


# ---------------------------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://collections.vam.ac.uk/item/O1/quilt/",  # V&A: rejected source
        "https://www.quiltindex.org/view/?type=fullrec",  # Quilt Index: rejected source
        "https://commons.wikimedia.org/wiki/File:Quilt.jpg",  # Commons: not on the allowlist
        "https://images.metmuseum.org.example.com/x.jpg",  # suffix trick
        "https://evilsi.edu/x.jpg",  # look-alike of the .si.edu suffix
        "http://images.metmuseum.org/x.jpg",  # plain http
    ],
)
def test_the_fetch_refuses_any_host_off_the_allowlist(url):
    with pytest.raises(cf.HostRefused):
        cf.check_host(url)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Unlabeled pairs read height x width, the museum convention for flat textiles:
        # 82 1/2 = 82.5 in high, 74 in wide.
        ("82 1/2 x 74 in. (209.6 x 188 cm)", (74.0, 82.5)),
        ("H. 80 x W. 70 in. (203.2 x 177.8 cm)", (70.0, 80.0)),
        # Labels win over order.
        ("W. 70 x H. 80 in.", (70.0, 80.0)),
        # Smithsonian physicalDescription shape: 84 high, 72 wide.
        ("overall: 84 in x 72 in; 213.36 cm x 182.88 cm", (72.0, 84.0)),
        # Smithsonian H x W x D shape: the depth (1/8 in) is dropped; 89 1/4 = 89.25 in high,
        # 61 3/4 = 61.75 in wide.
        ("H x W x D: 89 1/4 × 61 3/4 × 1/8 in. (226.7 × 156.8 × 0.3 cm)",
         (61.75, 89.25)),
        # AIC shape, with the multiplication sign: the inch pair is 80 x 72.
        ("203.2 × 182.9 cm (80 × 72 in.)", (72.0, 80.0)),
        # Centimetres only: 254 / 2.54 = 100.0 in high, 203.2 / 2.54 = 80.0 in wide.
        ("254 x 203.2 cm", (80.0, 100.0)),
        ("Dimensions unavailable", None),
    ],
)
def test_finished_sizes_parse_from_museum_dimensions(text, expected):
    assert cf.parse_finished_size(text) == expected


def test_finished_sizes_format_as_approximate_inches():
    # By hand: 72 and 80.5 print without trailing zeros, width first.
    assert cf.format_finished(72.0, 80.5) == "~72 x 80.5"


def test_the_rate_limiter_spaces_requests_one_second_apart():
    # By hand: interval 1.0 s; the first request goes at t = 0.0 with no wait; the second, asked
    # for at t = 0.3, waits 1.0 - 0.3 = 0.7 s; the third, asked for at t = 2.5, waits nothing.
    now, slept = [0.0], []

    def sleep(seconds):
        slept.append(round(seconds, 6))
        now[0] += seconds

    limiter = cf.RateLimiter(1.0, clock=lambda: now[0], sleep=sleep)
    limiter.wait()
    now[0] = 0.3
    limiter.wait()
    now[0] = 2.5
    limiter.wait()
    assert slept == [0.7]


# ---------------------------------------------------------------------------------------------
# Rights flags and candidates, from hand-written record fragments in each source's shape
# ---------------------------------------------------------------------------------------------

MET_RECORD = {
    "objectID": 11, "isPublicDomain": True, "title": "Quilt, Ohio Star pattern",
    "primaryImage": "https://images.metmuseum.org/CRDImages/ad/original/x.jpg",
    "objectURL": "https://www.metmuseum.org/art/collection/search/11",
    "creditLine": "Gift of a donor, 1970", "dimensions": "80 x 72 in. (203.2 x 182.9 cm)",
    "objectEndDate": 1850,
}
AIC_RECORD = {
    "id": 22, "is_public_domain": True, "image_id": "abc-123", "title": "Nine Patch Quilt",
    "date_end": 1880, "dimensions": "203.2 \u00d7 182.9 cm (80 \u00d7 72 in.)",
    "credit_line": "Gift of a donor",
}
SI_ROW = {
    "id": "edanmdm-nmah_1",
    "content": {
        "descriptiveNonRepeating": {
            "record_ID": "nmah_1", "title": {"content": "Double Irish Chain"},
            "record_link": "http://n2t.net/ark:/65665/x",
            "online_media": {"media": [{
                "type": "Images", "usage": {"access": "CC0"},
                "content": "https://ids.si.edu/ids/deliveryService?id=NMAH-1",
                "resources": [{"label": "High-resolution JPEG",
                               "url": "https://ids.si.edu/ids/download?id=NMAH-1.jpg"}],
            }]},
        },
        "indexedStructured": {"object_type": ["Quilts"]},
        "freetext": {
            "date": [{"label": "Date", "content": "1850s"}],
            "physicalDescription": [{"label": "Dimensions", "content": "overall: 84 in x 72 in"}],
            "creditLine": [{"label": "Credit Line", "content": "Gift of a donor"}],
        },
    },
}


def test_a_met_record_clears_only_on_is_public_domain_true():
    c = cf.met_candidate(MET_RECORD)
    assert (c.source, c.object_id, c.image_url, c.date_end) == (
        "met", "11", MET_RECORD["primaryImage"], 1850)
    for change in ({"isPublicDomain": False}, {"isPublicDomain": "true"}, {"primaryImage": ""}):
        with pytest.raises(cf.NotCleared):
            cf.met_candidate(MET_RECORD | change)


def test_an_aic_record_clears_on_is_public_domain_and_builds_its_iiif_url():
    # By hand: iiif base + image id + the 1686 px public-domain width.
    c = cf.aic_candidate(AIC_RECORD)
    assert c.image_url == "https://www.artic.edu/iiif/2/abc-123/full/1686,/0/default.jpg"
    assert c.landing_url == "https://www.artic.edu/artworks/22"
    for change in ({"is_public_domain": False}, {"image_id": None}):
        with pytest.raises(cf.NotCleared):
            cf.aic_candidate(AIC_RECORD | change)


def test_a_smithsonian_row_clears_on_a_cc0_image_medium():
    # By hand: the high-resolution JPEG wins over the delivery URL; "1850s" gives 1850; the
    # http ark link is replaced by the https record page.
    c = cf.si_candidate(SI_ROW)
    assert (c.object_id, c.image_url, c.date_end) == (
        "nmah_1", "https://ids.si.edu/ids/download?id=NMAH-1.jpg", 1850)
    assert c.landing_url == "https://collections.si.edu/search/detail/edanmdm-nmah_1"
    assert c.dimensions_text == "overall: 84 in x 72 in" and c.credit == "Gift of a donor"
    restricted = json.loads(json.dumps(SI_ROW))
    medium = restricted["content"]["descriptiveNonRepeating"]["online_media"]["media"][0]
    medium["usage"]["access"] = "Usage conditions apply"
    with pytest.raises(cf.NotCleared):
        cf.si_candidate(restricted)


def test_screening_keeps_quilts_made_before_1930_with_cleared_flags():
    # By hand: the Met quilt (1850) is kept; 1930 is the first modern year, 1929 is not; a
    # coverlet title is not a quilt at the Met; the Smithsonian pattern-titled row is a quilt
    # by object type.
    kept, skipped = cf.screen_records("met", [
        MET_RECORD,
        MET_RECORD | {"objectID": 12, "objectEndDate": 1930},
        MET_RECORD | {"objectID": 13, "objectEndDate": 1929},
        MET_RECORD | {"objectID": 14, "title": "Coverlet"},
        MET_RECORD | {"objectID": 15, "isPublicDomain": False},
    ])
    assert [c.object_id for c in kept] == ["11", "13"]
    assert skipped == {"made 1930 or later": 1, "title does not name a quilt": 1,
                       "isPublicDomain is not true": 1}
    assert [c.title for c in cf.screen_records("smithsonian", [SI_ROW])[0]] == [
        "Double Irish Chain"]


LACMA_PAGE = (
    '<script type="application/ld+json">{"@type":"VisualArtwork","name":"Quilt, \'Nine Patch\'",'
    '"creditText":"Gift of a donor","size":"78 3/4 x 72 3/4 in. (200 x 184.8 cm)",'
    '"dateCreated":"circa 1920"}</script>'
    '<script>self.__next_f.push([1,"{\\"desktop\\":\\"https://collections-images.lacma.org/'
    'images/54904/54904-1-desktop.jpg\\",\\"publicDomain\\":1}"])</script>'
    '<script>self.__next_f.push([1,"{\\"publicDomain\\":1,\\"copyrightText\\":\\"\\"}"])</script>'
)


def test_a_lacma_page_clears_only_when_every_public_domain_flag_is_1():
    # By hand: both flags read 1; "circa 1920" gives 1920; the desktop rendition is the image.
    c = cf.lacma_candidate({"object_id": "54904", "html": LACMA_PAGE})
    assert (c.title, c.date_end, c.credit) == ("Quilt, 'Nine Patch'", 1920, "Gift of a donor")
    assert c.image_url == "https://collections-images.lacma.org/images/54904/54904-1-desktop.jpg"
    restricted = LACMA_PAGE.replace('\\"publicDomain\\":1,', '\\"publicDomain\\":0,')
    assert restricted != LACMA_PAGE
    with pytest.raises(cf.NotCleared):
        cf.lacma_candidate({"object_id": "54904", "html": restricted})
