"""D3a corpus v0: the manifest, the annotations, the holdout rule and the fetch helpers.

Expected values are hand-computed in the comments beside each assertion; none comes from running
QREP. Record fragments and dimension strings are hand-written in the shapes the museum records
use; no saved third-party page is used. Every check that reads corpus/ reads the committed
files, so a row, an image or an annotation that breaks a rule fails here before corpus-guard runs.
"""

import hashlib
import io
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
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
ANNOTATIONS = sorted((CORPUS / "annotations").rglob("*.json"))
GOLD = sorted((CORPUS / "gold").rglob("*.json"))
IMAGES = sorted(p for p in (CORPUS / "images").glob("*") if p.name != ".gitkeep")


def rows() -> list[dict[str, str]]:
    return cf.read_manifest(MANIFEST)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------------------------
# Manifest columns and vocabularies
# ---------------------------------------------------------------------------------------------


def test_manifest_has_the_required_columns_in_order():
    # Source: plan D3a, criterion 4: file and license (corpus-guard), then the listed columns,
    # then eval_set last, which marks the annotated rows that form the v0 eval set.
    header = MANIFEST.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == [
        "file", "license", "source", "object_id", "title", "landing_url", "image_url",
        "rights_flag", "policy_url", "credit", "dimensions_text", "finished_in", "sha256",
        "file_sha256", "px_w", "px_h", "tier", "class", "capture", "commit_ok", "date_end",
        "eval_set",
    ]
    assert tuple(header) == cf.COLUMNS


MET_POLICY = "https://www.metmuseum.org/about-the-met/policies-and-documents/image-resources"
# Hand-written from each institution's terms (plan D3a, criterion 2; data-56): CC0-1.0 where the
# institution dedicates the image CC0 (Met, Smithsonian), PDM-1.0 where it marks the work public
# domain (AIC, LACMA), the per-object flag that clears an image, and the policy page that says so.
SOURCE_TERMS = {
    "met": ("CC0-1.0", "isPublicDomain=true", MET_POLICY),
    "smithsonian": ("CC0-1.0", "media.usage.access=CC0", "https://www.si.edu/openaccess"),
    "aic": ("PDM-1.0", "is_public_domain=true", "https://www.artic.edu/image-licensing"),
    "lacma": ("PDM-1.0", "publicDomain=1", "https://www.lacma.org/about/contact-us/terms-use"),
}


def test_every_row_licenses_by_its_source_flag():
    for row in rows():
        assert row["source"] in SOURCE_TERMS, row["file"]
        assert (row["license"], row["rights_flag"], row["policy_url"]) == SOURCE_TERMS[
            row["source"]], row["file"]


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


def test_finished_sizes_keep_their_source_text_and_follow_the_photo():
    # Source: plan D3a, criterion 4: parse finished sizes, keep the source text, mark approximate.
    # The longer side of the quilt is the longer side of the photo.
    for row in rows():
        if row["finished_in"]:
            assert row["finished_in"].startswith("~"), row["file"]
            assert row["dimensions_text"], row["file"]
            width, height = (float(n) for n in row["finished_in"][1:].split(" x "))
            px_w, px_h = int(row["px_w"]), int(row["px_h"])
            assert not (px_w > px_h and width < height), row["file"]
            assert not (px_w < px_h and width > height), row["file"]


def test_finished_sizes_rederive_from_dimensions_text():
    # Each row's finished_in is what build_rows derives from its own dimensions_text and pixel
    # size, so a hand edit to one without the other fails here.
    for row in rows():
        parsed = cf.parse_finished_size(row["dimensions_text"])
        expected = (cf.format_finished(*cf.orient(parsed, int(row["px_w"]), int(row["px_h"])))
                    if parsed else "")
        assert row["finished_in"] == expected, row["file"]


def test_every_row_predates_the_modern_cutoff():
    # Source: plan D3a, criterion 3 and data-55: no modern designer quilt. The fetch skips any
    # object made in 1930 or later, and any undated object, before fetching its image.
    for row in rows():
        assert row["date_end"].isdigit() and int(row["date_end"]) < 1930, row["file"]


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
    """The v0 eval set by tier: the rows whose eval_set column reads v0 (corpus/README.md). Every
    refusal carries proposals, so the set is marked in the manifest rather than read off which
    photos are annotated."""
    chosen: dict[str, list[dict[str, str]]] = {}
    for row in rows():
        assert row["eval_set"] in {"", "v0"}, row["file"]
        if row["eval_set"] == "v0":
            chosen.setdefault(row["tier"], []).append(row)
    return chosen


def test_the_v0_eval_set_holds_every_tier_a_photo_and_at_least_30_refusals():
    # Source: plan D3a, criterion 6: every tier A photo found, and at least 30 refusal photos
    # (G4 needs n of at least 30).
    chosen = eval_set()
    tier_a = [row["file"] for row in rows() if row["tier"] == "A"]
    assert tier_a and sorted(r["file"] for r in chosen.get("A", [])) == sorted(tier_a)
    assert len(chosen.get("R", [])) >= 30
    assert set(chosen) == {"A", "R"}
    annotated = {an.load(path).photo for path in ANNOTATIONS}
    assert all(row["file"] in annotated for tier in chosen.values() for row in tier)


def test_every_tier_a_and_refusal_photo_is_annotated():
    # Source: plan D3a, criterion 8: proposals on every tier A photo and the class on every
    # refusal photo, so each of those rows has an annotation file.
    annotated = {an.load(path).photo for path in ANNOTATIONS}
    missing = [row["file"] for row in rows() if row["tier"] in {"A", "R"}
               and row["file"] not in annotated]
    assert missing == []


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


# The v0 holdout, frozen here so that rewriting a row's sha256 cannot move a photo into or out
# of it unnoticed. Each entry is the photo stem and the first 8 hex digits of its source
# image's sha256, copied from corpus/manifest.csv; the comment is the hand check that the
# prefix read as an integer is a multiple of 3 (plan D3a, criterion 9).
HOLDOUT_V0 = {
    "lacma-30012": "856dc71b",  # 2238564123 = 3 x 746188041
    "lacma-33726": "54f1e8d3",  # 1425139923 = 3 x 475046641
    "lacma-52522": "0ceea295",  # 216965781 = 3 x 72321927
    "lacma-54813": "8f9ad7a6",  # 2409289638 = 3 x 803096546
    "lacma-56077": "182ebed9",  # 405716697 = 3 x 135238899
    "lacma-59557": "7f23591f",  # 2133023007 = 3 x 711007669
    "lacma-63255": "9d548225",  # 2639561253 = 3 x 879853751
    "met-13617": "b40a8ebe",  # 3020590782 = 3 x 1006863594
    "met-13622": "18ac9758",  # 413964120 = 3 x 137988040
    "met-13854": "43e7b5c1",  # 1139258817 = 3 x 379752939
    "met-13861": "c3d6319d",  # 3285594525 = 3 x 1095198175
    "met-13864": "93b7e9f7",  # 2478303735 = 3 x 826101245
    "met-13869": "74f85543",  # 1962431811 = 3 x 654143937
    "met-13870": "b62c90a4",  # 3056373924 = 3 x 1018791308
    "met-13872": "4318202d",  # 1125654573 = 3 x 375218191
    "met-13875": "778dd41a",  # 2005783578 = 3 x 668594526
    "met-13876": "389f6adb",  # 949971675 = 3 x 316657225
    "met-13878": "e6a50127",  # 3869573415 = 3 x 1289857805
    "met-13881": "23f7ca65",  # 603441765 = 3 x 201147255
    "met-13884": "1ce68721",  # 484869921 = 3 x 161623307
    "met-13889": "0caf8b07",  # 212830983 = 3 x 70943661
    "met-13894": "c3dde707",  # 3286099719 = 3 x 1095366573
    "met-13904": "4feba375",  # 1340842869 = 3 x 446947623
    "met-13912": "7263f300",  # 1919152896 = 3 x 639717632
    "met-14129": "d8c3c83a",  # 3636709434 = 3 x 1212236478
    "met-14200": "22af3259",  # 581907033 = 3 x 193969011
    "met-14827": "ede5f2b1",  # 3991270065 = 3 x 1330423355
    "met-16295": "dca29cc8",  # 3701644488 = 3 x 1233881496
    "met-16683": "ee568b59",  # 3998649177 = 3 x 1332883059
    "met-18956": "bcfbec09",  # 3170626569 = 3 x 1056875523
    "met-219121": "261086c7",  # 638617287 = 3 x 212872429
    "met-219512": "b3c7134d",  # 3016168269 = 3 x 1005389423
    "met-221867": "37c59fbd",  # 935698365 = 3 x 311899455
    "met-227076": "e74912b3",  # 3880325811 = 3 x 1293441937
    "met-229930": "2a73b20d",  # 712225293 = 3 x 237408431
    "met-669875": "9b0ee59a",  # 2601444762 = 3 x 867148254
    "met-70388": "4ad5ea1c",  # 1255533084 = 3 x 418511028
    "met-70390": "2bdf33d0",  # 736048080 = 3 x 245349360
    "met-814560": "63182601",  # 1662526977 = 3 x 554175659
    "met-854563": "63264ab9",  # 1663453881 = 3 x 554484627
    "met-854565": "c552dd40",  # 3310542144 = 3 x 1103514048
    "met-854566": "dfe01b7e",  # 3756006270 = 3 x 1252002090
    "met-854567": "82ae71ea",  # 2192470506 = 3 x 730823502
    "met-854570": "658f4754",  # 1703888724 = 3 x 567962908
    "met-855677": "0c8f684d",  # 210724941 = 3 x 70241647
    "met-864828": "d5e715ba",  # 3588691386 = 3 x 1196230462
    "met-864830": "4e441dd7",  # 1313086935 = 3 x 437695645
    "met-864831": "41c60dc9",  # 1103498697 = 3 x 367832899
    "smithsonian-chndm-1951-46-1": "c008767b",  # 3221780091 = 3 x 1073926697
    "smithsonian-chndm-1955-14-6": "f48ddb4d",  # 4102937421 = 3 x 1367645807
    "smithsonian-chndm-1957-78-1": "e479df9d",  # 3833192349 = 3 x 1277730783
    "smithsonian-chndm-1960-73-2": "56831019",  # 1451429913 = 3 x 483809971
    "smithsonian-chndm-1962-184-1": "0b586bdc",  # 190344156 = 3 x 63448052
    "smithsonian-chndm-1973-25-1": "c2e37250",  # 3269685840 = 3 x 1089895280
    "smithsonian-chndm-1975-16-2": "9e6f3b05",  # 2658089733 = 3 x 886029911
    "smithsonian-chndm-1978-167-1": "ebdbf413",  # 3957060627 = 3 x 1319020209
    "smithsonian-nmaahc-2017-108-5": "c700d109",  # 3338719497 = 3 x 1112906499
    "smithsonian-nmah-556181": "577b5820",  # 1467701280 = 3 x 489233760
    "smithsonian-nmah-556246": "60b39ef2",  # 1622384370 = 3 x 540794790
    "smithsonian-nmah-556267": "a0f0a14e",  # 2700124494 = 3 x 900041498
    "smithsonian-nmah-556283": "266161c2",  # 643916226 = 3 x 214638742
    "smithsonian-nmah-556322": "69b552af",  # 1773490863 = 3 x 591163621
    "smithsonian-nmah-556330": "9c36d51b",  # 2620839195 = 3 x 873613065
    "smithsonian-nmah-556331": "d16b8a80",  # 3513485952 = 3 x 1171161984
    "smithsonian-nmah-556351": "27bce2e7",  # 666690279 = 3 x 222230093
    "smithsonian-nmah-556592": "1b43625d",  # 457400925 = 3 x 152466975
    "smithsonian-nmah-556599": "913509bd",  # 2436172221 = 3 x 812057407
    "smithsonian-nmah-640707": "82392d4a",  # 2184785226 = 3 x 728261742
    "smithsonian-saam-1987-80": "32a50e92",  # 849677970 = 3 x 283225990
    "smithsonian-saam-1998-149-1": "43d209cb",  # 1137838539 = 3 x 379279513
    "smithsonian-saam-1998-149-11": "779e7664",  # 2006873700 = 3 x 668957900
    "smithsonian-saam-1998-149-13": "094a5032",  # 155865138 = 3 x 51955046
    "smithsonian-saam-1998-149-14": "c817de92",  # 3357007506 = 3 x 1119002502
    "smithsonian-saam-1998-149-15": "4b2a2634",  # 1261053492 = 3 x 420351164
    "smithsonian-saam-1998-149-16": "19754b98",  # 427117464 = 3 x 142372488
    "smithsonian-saam-1998-149-17": "aa05079a",  # 2852456346 = 3 x 950818782
    "smithsonian-saam-1998-149-19": "366cd0d4",  # 913101012 = 3 x 304367004
    "smithsonian-saam-1998-149-28": "923f2ccb",  # 2453613771 = 3 x 817871257
    "smithsonian-saam-1998-149-30": "3a2e2497",  # 976102551 = 3 x 325367517
    "smithsonian-saam-1998-149-5": "e1ab510f",  # 3786101007 = 3 x 1262033669
    "smithsonian-saam-1998-149-7": "6d80bca3",  # 1837153443 = 3 x 612384481
    "smithsonian-saam-2013-67-10": "5faf0c51",  # 1605307473 = 3 x 535102491
    "smithsonian-saam-2016-5-42": "a61f67c6",  # 2787076038 = 3 x 929025346
    "smithsonian-saam-2016-57-10": "24282828",  # 606611496 = 3 x 202203832
    "smithsonian-saam-2016-57-2": "bff136de",  # 3220256478 = 3 x 1073418826
    "smithsonian-saam-2016-57-9": "ccbe4ca6",  # 3435023526 = 3 x 1145007842
    "smithsonian-saam-2017-24-2": "b30f1ecd",  # 3004112589 = 3 x 1001370863
    "smithsonian-saam-2017-24-3": "7d06fefb",  # 2097610491 = 3 x 699203497
    "smithsonian-saam-2017-24-32": "e5e6e64f",  # 3857114703 = 3 x 1285704901
    "smithsonian-saam-2017-24-4": "14c4bc73",  # 348437619 = 3 x 116145873
}


def test_the_holdout_is_pinned_photo_by_photo():
    # Source: plan D3a, criterion 9. Membership by the rule must equal the pinned set, each pinned
    # prefix must still be its row's, and each pinned prefix must be a multiple of 3 by plain
    # integer arithmetic, independent of an.in_holdout.
    by_stem = {Path(row["file"]).stem: row for row in rows()}
    assert {stem for stem, row in by_stem.items() if an.in_holdout(row["sha256"])} == set(HOLDOUT_V0)
    for stem, prefix in HOLDOUT_V0.items():
        assert by_stem[stem]["sha256"][:8] == prefix, stem
        assert int(prefix, 16) % 3 == 0, stem


def test_readme_reports_the_holdout_count_of_each_tier():
    # The README's v0 counts table ends each tier row with its holdout count; they must be the
    # pinned set's counts, so a stale table fails here.
    by_stem = {Path(row["file"]).stem: row for row in rows()}
    expected = {tier: sum(by_stem[s]["tier"] == tier for s in HOLDOUT_V0) for tier in cf.TIERS}
    text = (CORPUS / "README.md").read_text(encoding="utf-8")
    reported = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] in cf.TIERS and cells[-1].isdigit() and cells[1].isdigit():
            reported[cells[0]] = int(cells[-1])
    assert reported == expected


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
    # Staged at the canvas size, the corners scale by 1000 / 1000 = 1 and 800 / 800 = 1, so they
    # stay as OUTER gives them.
    request = an.to_read_request(parse(sample()), "photo.png", (1000, 800))
    assert isinstance(request, ReadRequest)
    assert request.frame == OuterEdgeFrame.model_validate_json(json.dumps(OUTER))
    assert [band.width_squares for band in request.frame.bands] == [1.0, 0.5]
    assert (request.crop_offset.x, request.crop_offset.y) == (0.0, 0.0)
    assert (request.counts.blocks_across, request.counts.blocks_down) == (8, 6)
    assert (request.counts.squares_per_block_across, request.counts.squares_per_block_down) == (5, 5)
    assert request.fabric_count == 3
    assert request.token == "photo.png"


def test_the_field_frame_maps_when_its_corners_were_confirmed():
    request = an.to_read_request(parse(sample()), "photo.png", (1000, 800), frame="field")
    assert request.frame.kind == "field"
    assert (request.frame.corners.top_left.x, request.frame.corners.top_left.y) == (130.0, 80.0)


def test_corners_scale_from_the_canvas_to_the_staged_image():
    # A committed copy downsized from a 3873 x 4096 scan to 756 x 800. The corners are in order
    # and convex on that canvas (top left 30 < top right 3840 across, 40 < 4000 down the left).
    # By hand, bottom right (3845, 4009):
    # x = 3845 * 756 / 3873 = 2,906,820 / 3873; 3873 * 750 = 2,904,750, remainder 2,070, and
    # 2,070 / 3873 = 0.5345, so x = 750.5345.
    # y = 4009 * 800 / 4096 = 3,207,200 / 4096; 4096 * 783 = 3,207,168, remainder 32, and
    # 32 / 4096 = 0.0078125, so y = 783.0078125.
    edge = {"kind": "outer_edge", "bands": [], "corners": {
        "top_left": {"x": 30, "y": 40}, "top_right": {"x": 3840, "y": 35},
        "bottom_right": {"x": 3845, "y": 4009}, "bottom_left": {"x": 25, "y": 4000}}}
    doc = sample(canvas=[3873, 4096],
                 frame=[{"value": {"outer_edge": edge}, "provenance": "verified-jake"}])
    corner = an.to_read_request(parse(doc), "copy.jpg", (756, 800)).frame.corners.bottom_right
    assert corner.x == pytest.approx(750.5345, abs=1e-3)
    assert corner.y == pytest.approx(783.0078125, abs=1e-3)


def test_a_proposal_stands_in_for_truth_only_when_asked():
    doc = sample(frame=[sample()["frame"][1]], counts=[sample()["counts"][1]], fabrics=[])
    with pytest.raises(ValueError):
        an.to_read_request(parse(doc), "photo.png", (1000, 800))
    # By hand: proposed-a counts blocks_across 7, and no fabric claim leaves the count unset.
    request = an.to_read_request(parse(doc), "photo.png", (1000, 800), prefer=("proposed-a",))
    assert request.counts.blocks_across == 7 and request.fabric_count is None


def test_only_verified_corners_and_counts_count_as_truth_by_default():
    # Source: plan section 5.D: gate truth for corners, bands and counts is verified-jake only.
    doc = sample(frame=[sample()["frame"][0] | {"provenance": "hand-authored"}],
                 counts=[sample()["counts"][0] | {"provenance": "adjudicated"}])
    with pytest.raises(ValueError):
        an.to_read_request(parse(doc), "photo.png", (1000, 800))


@pytest.mark.parametrize("count", [1, 13])
def test_a_fabric_count_outside_the_reads_range_is_left_to_the_read(count):
    # Source: qrep/contract.py FABRICS_MIN = 2 and FABRICS_MAX = 12; 1 and 13 fall outside.
    doc = sample(fabrics=[{"value": {"count": count}, "provenance": "verified-jake"}])
    assert an.to_read_request(parse(doc), "photo.png", (1000, 800)).fabric_count is None


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


def test_the_sidecar_view_has_no_character_for_an_out_of_scope_photo():
    # The sidecar vocabulary (squares, non_square, no_pattern, garbage) has no word for a refusal.
    doc = sample(construction_class=[{"value": "out_of_scope", "provenance": "verified-jake"}])
    assert an.sidecar_view(parse(doc))["character"] is None


def test_the_sidecar_view_leaves_border_pitches_unknown_without_a_frame():
    # By hand from sample() with no frame: rows = 6 x 5 = 30 and cols = 8 x 5 = 40 still follow
    # from the counts, but no frame gives the bands, so border_pitches is None, and so is quad.
    view = an.sidecar_view(parse(sample(frame=[])))
    assert view["grid"] == {"rows": 30, "cols": 40, "border_pitches": None}
    assert view["quad"] is None


def test_a_stored_sidecar_claim_wins_over_the_derived_value():
    # hst would derive non_square; the verified-jake character claim says no_pattern.
    doc = sample(character=[{"value": "no_pattern", "provenance": "verified-jake"}])
    assert an.sidecar_view(parse(doc))["character"] == "no_pattern"


def outer(**corners) -> dict:
    return OUTER | {"corners": OUTER["corners"] | corners}


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
        # top_left and top_right swapped: top left x 900 is not left of top right x 100.
        {"frame": [{"value": {"outer_edge": outer(
            top_left={"x": 900, "y": 60}, top_right={"x": 100, "y": 50})},
            "provenance": "proposed-b"}]},
        # A bow-tie: bottom_right and bottom_left swapped, so the left and right sides cross;
        # bottom left x 890 is not left of bottom right x 110.
        {"frame": [{"value": {"outer_edge": outer(
            bottom_right={"x": 110, "y": 740}, bottom_left={"x": 890, "y": 750})},
            "provenance": "proposed-b"}]},
        # A flat quad: top left (100, 50), top right (500, 400) and bottom right (900, 750) lie
        # on one line, each step +400 across and +350 down; the cross product of top left to
        # top right with top left to bottom right is (500 - 100) x (750 - 50) - (400 - 50) x
        # (900 - 100) = 400 x 700 - 350 x 800 = 280,000 - 280,000 = 0. The order holds
        # (100 < 500, 110 < 900, 50 < 740, 400 < 750), so only the flatness refuses it.
        {"frame": [{"value": {"outer_edge": outer(
            top_right={"x": 500, "y": 400}, bottom_right={"x": 900, "y": 750})},
            "provenance": "proposed-b"}]},
        # Field corners outside the outer edge: field top left (50, 80) lies left of the outer
        # edge's left side, bottom left (110, 740) to top left (100, 50); the cross product is
        # (100 - 110) x (80 - 740) - (50 - 740) x (50 - 110) = 6,600 - 41,400 = -34,800 < 0.
        {"frame": [{"value": {"outer_edge": OUTER, "field": FIELD | {
            "corners": FIELD["corners"] | {"top_left": {"x": 50, "y": 80}}}},
            "provenance": "proposed-b"}]},
        # A mask point off the 1000 x 800 canvas (x = 1001).
        {"masks": [{"value": [{"polygon": [{"x": 10, "y": 10}, {"x": 1001, "y": 10},
                                           {"x": 10, "y": 20}], "reason": "label"}],
                    "provenance": "hand-authored"}]},
        # other is not one of plan D3a's six refusal classes.
        {"refusal_class": [{"value": "other", "provenance": "proposed-a"}]},
    ],
)
def test_the_annotation_model_refuses_malformed_input(change):
    with pytest.raises(ValidationError):
        parse(sample(**change))


def test_the_committed_schema_is_the_models_export():
    # Source: plan D3a, criterion 7: the model exports corpus/schema/annotation.schema.json, which
    # the dev annotate page (C3a) writes against; a drift between them fails here.
    # Compared as parsed JSON, not text: the Pyodide build of pydantic prints a float bound as 0
    # where the native build prints 0.0, and the two are the same schema.
    committed = json.loads((CORPUS / "schema" / "annotation.schema.json").read_text(encoding="utf-8"))
    assert committed == an.schema()


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
    # The sample's canvas is [1000, 800]; a row of 999 x 800 binds another size.
    other_size = {k: v | {"px_w": "999"} for k, v in licensed.items()}
    problems = an.licensed_photo_problems(parse(sample()), "met-1", other_size)
    assert len(problems) == 1 and "canvas" in problems[0]


def test_the_licensed_photo_rule_reads_a_gold_layout_by_its_identity_keys():
    # A D3b gold layout is its own format; only photo, sha256 and canvas are read, so extra keys
    # pass and a missing canvas is a problem.
    licensed = {"private/cache/met-1.jpg": {"license": "CC0-1.0", "sha256": SHA,
                                            "px_w": "1000", "px_h": "800"}}
    gold = {"photo": "private/cache/met-1.jpg", "sha256": SHA, "canvas": [1000, 800],
            "tiles": [{"row": 0, "col": 0, "fabric": 1}], "layout": {"rows": 30, "cols": 40}}
    assert an.licensed_photo_problems(gold, "met-1", licensed) == []
    no_canvas = {k: v for k, v in gold.items() if k != "canvas"}
    assert len(an.licensed_photo_problems(no_canvas, "met-1", licensed)) == 1


def test_every_committed_annotation_names_a_licensed_photo():
    # The issue #113 rule, applied by this test until corpus-guard enforces it: every committed
    # annotation or gold JSON, in any subfolder, names a photo with a CC0-1.0 or PDM-1.0 row whose
    # sha256 and canvas match, under the photo's own stem. Gold files are read as plain JSON,
    # because D3b's gold layouts are not annotations.
    by_file = {row["file"]: row for row in rows()}
    assert ANNOTATIONS
    docs = [(path, an.load(path)) for path in ANNOTATIONS] + [
        (path, json.loads(path.read_text(encoding="utf-8"))) for path in GOLD]
    for path, doc in docs:
        problems = an.licensed_photo_problems(doc, path.stem, by_file)
        assert problems == [], (path.name, problems)


def test_annotation_finished_sizes_match_their_rows():
    # A source-record finished size is copied from the row: its source_text is the row's
    # dimensions_text, and its width and height print as the row's finished_in does (format
    # "~{w:g} x {h:g}" after rounding each to 2 places, plan D3a criterion 4's approximate mark).
    by_file = {row["file"]: row for row in rows()}
    for path in ANNOTATIONS:
        doc = an.load(path)
        row = by_file[doc.photo]
        for claim in doc.finished_size:
            if claim.provenance != "source-record":
                continue
            size = claim.value
            assert size.source_text == row["dimensions_text"], path.name
            printed = f"~{round(size.width_in, 2):g} x {round(size.height_in, 2):g}"
            assert printed == row["finished_in"], path.name


def test_tier_a_and_refusal_photos_carry_two_independent_proposals():
    # Source: plan D3a, criterion 8: proposed-a and proposed-b for corners, bands, counts and
    # class on every tier A photo, and the class on every refusal photo.
    by_file = {row["file"]: row for row in rows()}
    for path in ANNOTATIONS:
        doc = an.load(path)
        tier = by_file[doc.photo]["tier"]
        needed = ("frame", "counts", "construction_class") if tier == "A" else (
            "construction_class",)
        for name in needed:
            codes = {claim.provenance for claim in getattr(doc, name)}
            assert {"proposed-a", "proposed-b"} <= codes, (path.name, name)
        # A proposal that calls the photo out of scope names its refusal class too; one that
        # calls a refusal in scope is a disagreement corpus/README.md lists for D3b.
        refused = {c.provenance for c in doc.construction_class if c.value == "out_of_scope"}
        named = {c.provenance for c in doc.refusal_class}
        assert refused == named, path.name


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
        # Feet and inches: 8 ft 3 1/2 in = 8 x 12 + 3.5 = 99.5 in high; 98 1/4 = 98.25 in wide.
        ("8 ft. 3 1/2 in. \u00d7 98 1/4 in.", (98.25, 99.5)),
        # Unlabeled pairs read height x width, the museum convention for flat textiles:
        # 82 1/2 = 82.5 in high, 74 in wide.
        ("82 1/2 x 74 in. (209.6 x 188 cm)", (74.0, 82.5)),
        ("H. 80 x W. 70 in. (203.2 x 177.8 cm)", (70.0, 80.0)),
        # Labels win over order.
        ("W. 70 x H. 80 in.", (70.0, 80.0)),
        # L. (length) reads as the height: a museum that gives L x W for a flat textile names
        # its long side, which hangs down, so 80 in is the height and 70 in the width.
        ("L. 80 x W. 70 in.", (70.0, 80.0)),
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


@pytest.mark.parametrize(
    ("size", "canvas", "expected"),
    [
        # Landscape photo (1000 x 800): the longer 80 in side runs across.
        ((72.0, 80.0), (1000, 800), (80.0, 72.0)),
        # Portrait photo (800 x 1000): the longer side runs down; already so.
        ((72.0, 80.0), (800, 1000), (72.0, 80.0)),
        # Square photo: the museum's order stands.
        ((72.0, 80.0), (900, 900), (72.0, 80.0)),
    ],
)
def test_finished_sizes_turn_to_match_the_photo(size, canvas, expected):
    assert cf.orient(size, *canvas) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # A two-digit range end: 1925-35 ends in 1935.
        ("c. 1925-35", 1935),
        # The same range with an en dash, as museum records often write it: 1935.
        ("c. 1925\u201335", 1935),
        # A century ends with its last year: the 19th century with 1900.
        ("first half of 19th century", 1900),
        ("20th century", 2000),
        # A decade ends with its last year: 1850 + 9 = 1859.
        ("1850s", 1859),
        # A plain year stays as written.
        ("1848", 1848),
    ],
)
def test_dates_read_their_last_year(text, expected):
    assert max(cf._years(text)) == expected


def test_the_class_vocabularies_are_the_plans():
    # Source: plan D3a, criterion 5: the six refusal classes, and nothing else, so a tier R row
    # always names one the annotation format accepts. whole_cloth and outside_classes exclude a
    # photo that has no piecing, or whose refusal none of the six names.
    refusals = ("on_point", "curve", "applique", "medallion", "hexagon", "diamond_star")
    assert cf.REFUSALS == refusals and an.REFUSAL_CLASSES == refusals
    assert cf.EXCLUSIONS == ("partial_view", "duplicate", "not_a_quilt", "unreadable",
                             "whole_cloth", "outside_classes")


def test_undated_and_modern_objects_are_skipped():
    # By hand: 1929 is kept, 1930 is the first modern year, and no date at all is skipped too.
    kept, skipped = cf.screen_records("met", [
        MET_RECORD | {"objectID": 1, "objectEndDate": 1929},
        MET_RECORD | {"objectID": 2, "objectEndDate": 1930},
        MET_RECORD | {"objectID": 3, "objectEndDate": None},
    ])
    assert [c.object_id for c in kept] == ["1"]
    assert skipped == {"made 1930 or later, or undated": 2}


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
    # By hand: the high-resolution JPEG wins over the delivery URL; "1850s" gives the decade's
    # last year, 1850 + 9 = 1859; the http ark link is replaced by the https record page.
    c = cf.si_candidate(SI_ROW)
    assert (c.object_id, c.image_url, c.date_end) == (
        "nmah_1", "https://ids.si.edu/ids/download?id=NMAH-1.jpg", 1859)
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
    assert skipped == {"made 1930 or later, or undated": 1, "title does not name a quilt": 1,
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


# ---------------------------------------------------------------------------------------------
# Recheck, verify and redirects, with a fake client (no network)
# ---------------------------------------------------------------------------------------------


@dataclass
class Answer:
    """A fake response whose final URL or status differs from a plain 200 at the asked URL."""

    url: str
    status: int = 200
    body: bytes = b"page"


class FakeClient:
    """Answers by URL: bytes or a JSON value is a 200 at that URL, an exception is raised, and
    an Answer gives its own final URL and status. Every request's headers are recorded."""

    def __init__(self, pages):
        self.pages = pages
        self.requests = {}
        self.sent: list[tuple[str, dict]] = []

    def get_final(self, url, headers=None):
        self.sent.append((url, dict(headers or {})))
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        if isinstance(page, Answer):
            return page.body, page.url, page.status
        return (page if isinstance(page, bytes) else json.dumps(page).encode()), url, 200

    def get(self, url, headers=None):
        return self.get_final(url, headers)[0]

    def json(self, url, headers=None):
        return json.loads(self.get(url, headers))


MET_OBJECT = f"{cf.MET}/v1/objects/11"


def met_row(**changes) -> dict[str, str]:
    license, flag, policy = SOURCE_TERMS["met"]
    return {"file": "private/cache/met-11.jpg", "source": "met", "object_id": "11",
            "license": license, "rights_flag": flag, "policy_url": policy} | changes


def pages(record, policy=b"policy page"):
    return {MET_OBJECT: record, MET_POLICY: policy}


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "status", None, None)


def test_the_recheck_passes_an_unchanged_record(tmp_path):
    assert cf.recheck(FakeClient(pages(MET_RECORD)), [met_row()], tmp_path) == []


def test_the_recheck_fails_when_a_flag_no_longer_clears(tmp_path):
    # By hand: the live record says isPublicDomain false, so its flag renders
    # isPublicDomain=false against the row's isPublicDomain=true.
    problems = cf.recheck(FakeClient(pages(MET_RECORD | {"isPublicDomain": False})),
                          [met_row()], tmp_path)
    assert problems == ["private/cache/met-11.jpg: rights flag changed from isPublicDomain=true "
                        "to isPublicDomain=false"]


def test_the_recheck_compares_the_live_flag_with_the_rows_own_flag(tmp_path):
    # The record still clears (isPublicDomain true), but the row recorded another flag string, so
    # the row no longer states what the record says.
    problems = cf.recheck(FakeClient(pages(MET_RECORD)),
                          [met_row(rights_flag="isPublicDomain=yes")], tmp_path)
    assert problems == ["private/cache/met-11.jpg: rights flag changed from isPublicDomain=yes "
                        "to isPublicDomain=true"]


def test_the_recheck_fails_when_a_row_records_another_license(tmp_path):
    problems = cf.recheck(FakeClient(pages(MET_RECORD)), [met_row(license="PDM-1.0")], tmp_path)
    assert len(problems) == 1 and "PDM-1.0" in problems[0]


def test_a_record_that_cannot_be_fetched_is_one_problem_not_a_traceback(tmp_path):
    client = FakeClient(pages(http_error(MET_OBJECT, 404)))
    problems = cf.recheck(client, [met_row()], tmp_path)
    assert len(problems) == 1
    assert problems[0].startswith("private/cache/met-11.jpg:") and "404" in problems[0]


@pytest.mark.parametrize(
    ("policy", "says"),
    [
        (http_error(MET_POLICY, 404), "404"),  # gone
        (http_error(MET_POLICY, 403), "403"),  # blocks scripted reads: its terms are unconfirmed
        (http_error(MET_POLICY, 429), "429"),  # rate limited: unconfirmed too
        (urllib.error.URLError("no route"), "unreachable"),
        (Answer("https://www.metmuseum.org/"), "redirects"),  # moved to another URL
        (Answer(MET_POLICY, status=203), "203"),  # a success that is not a plain 200
    ],
)
def test_the_recheck_fails_closed_on_a_policy_page(tmp_path, policy, says):
    problems = cf.recheck(FakeClient(pages(MET_RECORD, policy)), [met_row()], tmp_path)
    assert len(problems) == 1 and says in problems[0] and MET_POLICY in problems[0]


def test_the_recheck_reads_each_policy_page_the_rows_cite_once(tmp_path):
    # Two Met rows cite one policy page, so it is requested once; it is the row's URL that is
    # read, whatever the code's own constant says.
    both = [met_row(), met_row(file="private/cache/met-12.jpg", object_id="12")]
    client = FakeClient(pages(MET_RECORD) | {
        f"{cf.MET}/v1/objects/12": MET_RECORD | {"objectID": 12}})
    assert cf.recheck(client, both, tmp_path) == []
    assert [url for url, _ in client.sent].count(MET_POLICY) == 1


def test_the_recheck_fails_when_a_lacma_page_turns_restricted(tmp_path):
    # By hand: the restricted page's two publicDomain flags read 1 and 0, so the live flag
    # renders publicDomain=1,0.
    license, flag, policy = SOURCE_TERMS["lacma"]
    row = {"file": "private/cache/lacma-54904.jpg", "source": "lacma", "object_id": "54904",
           "license": license, "rights_flag": flag, "policy_url": policy}
    restricted = LACMA_PAGE.replace('\\"publicDomain\\":1,', '\\"publicDomain\\":0,')
    client = FakeClient({"https://collections.lacma.org/object/54904": restricted.encode(),
                         policy: b"policy page"})
    problems = cf.recheck(client, [row], tmp_path)
    assert problems == ["private/cache/lacma-54904.jpg: rights flag changed from publicDomain=1 "
                        "to publicDomain=1,0"]


@pytest.mark.parametrize(
    ("source", "record", "expected"),
    [
        ("met", MET_RECORD, "isPublicDomain=true"),
        ("met", {"objectID": 11}, "isPublicDomain=missing"),
        ("aic", AIC_RECORD | {"is_public_domain": False}, "is_public_domain=false"),
        ("smithsonian", SI_ROW, "media.usage.access=CC0"),
        ("smithsonian", {"content": {}}, "media.usage.access=missing"),
        ("lacma", {"object_id": "1", "html": "no flags here"}, "publicDomain=missing"),
    ],
)
def test_the_live_flag_renders_what_the_record_says(source, record, expected):
    assert cf.live_flag(source, record) == expected


def test_verify_finds_a_cached_image_whose_bytes_changed(tmp_path):
    # By hand: the row binds sha256(b"abc"); the cache holds b"abd", so one problem; then the
    # right bytes give none, and a missing file gives one.
    row = met_row(sha256=hashlib.sha256(b"abc").hexdigest())
    (tmp_path / "met-11.jpg").write_bytes(b"abd")
    assert len(cf.verify(tmp_path, [row])) == 1
    (tmp_path / "met-11.jpg").write_bytes(b"abc")
    assert cf.verify(tmp_path, [row]) == []
    assert len(cf.verify(tmp_path / "empty", [row])) == 1


def aic_item(object_id: str, image_id: str) -> cf.Candidate:
    return cf.Candidate(
        "aic", object_id, "Nine Patch Quilt", f"https://www.artic.edu/artworks/{object_id}",
        f"https://www.artic.edu/iiif/2/{image_id}/full/1686,/0/default.jpg", "Gift of a donor",
        "", 1880)


def test_download_caches_only_valid_images_and_names_itself_to_aic(tmp_path):
    # A 3 x 2 PNG made here is a valid image; a challenge page answered with 200 is not, so it is
    # reported and never cached, where it would block every later fetch of that image.
    buffer = io.BytesIO()
    Image.new("RGB", (3, 2), "white").save(buffer, "PNG")
    png = buffer.getvalue()
    good, bad = aic_item("22", "abc"), aic_item("23", "def")
    cf.save_candidates(tmp_path, [good, bad])
    client = FakeClient({good.image_url: png, bad.image_url: b"<html>challenge</html>"})
    report = cf.download(client, tmp_path, ["aic"])
    assert report["fetched"] == 1 and list(report["failed"]) == ["aic-23.jpg"]
    assert (tmp_path / "aic-22.jpg").read_bytes() == png
    assert not (tmp_path / "aic-23.jpg").exists()
    saved = {c.object_id: c for c in cf.load_candidates(tmp_path)}
    assert (saved["22"].sha256, saved["22"].px_w, saved["22"].px_h) == (
        hashlib.sha256(png).hexdigest(), 3, 2)
    assert saved["23"].sha256 == ""
    # AIC asks every client, image requests included, to name itself in AIC-User-Agent.
    assert len(client.sent) == 2
    assert all("AIC-User-Agent" in headers for _, headers in client.sent)


def test_rows_refuse_a_screen_decision_with_no_fetched_candidate(tmp_path):
    cf.save_candidates(tmp_path, [])
    screen = tmp_path / "screen.csv"
    screen.write_text("stem,tier,class,commit_ok\nmet-11,A,squares,no\n", encoding="utf-8")
    with pytest.raises(ValueError, match="met-11"):
        cf.build_rows(tmp_path, screen, {})


def test_merging_rows_replaces_a_rescreened_photo_and_adds_a_new_one():
    # By hand: met 11 is screened again (tier B to A), so its new row replaces the old; aic 22 is
    # not screened again and stays; lacma 2048 is new and is added: three rows.
    old = [{"source": "met", "object_id": "11", "tier": "B"},
           {"source": "aic", "object_id": "22", "tier": "A"}]
    new = [{"source": "met", "object_id": "11", "tier": "A"},
           {"source": "lacma", "object_id": "2048", "tier": "R"}]
    merged = sorted(cf.merge_rows(old, new), key=lambda r: (r["source"], r["object_id"]))
    assert merged == [{"source": "aic", "object_id": "22", "tier": "A"},
                      {"source": "lacma", "object_id": "2048", "tier": "R"},
                      {"source": "met", "object_id": "11", "tier": "A"}]


def test_views_are_written_only_inside_the_ignored_private_folder(tmp_path):
    # default_cache() is <main checkout>/corpus/private/cache, so cache/views/x.png lies inside
    # the ignored corpus/private/ and passes.
    cache = cf.default_cache()
    inside = cache / "views" / "x.png"
    assert cf.require_private(inside) == inside
    # cache/../.. is corpus/private/cache -> corpus/private -> corpus, so the climbing path is
    # corpus/images/x.png, outside corpus/private/; tmp_path and the repo's own corpus/images/
    # are outside it too.
    for outside in (tmp_path / "x.png", REPO / "corpus" / "images" / "x.png",
                    cache / ".." / ".." / "images" / "x.png"):
        with pytest.raises(cf.NotPrivate):
            cf.require_private(outside)


def test_a_redirect_off_the_allowlist_is_refused():
    request = urllib.request.Request("https://images.metmuseum.org/x.jpg")
    with pytest.raises(cf.HostRefused):
        cf._AllowlistRedirects().redirect_request(
            request, None, 302, "Found", {}, "https://example.com/x.jpg")
