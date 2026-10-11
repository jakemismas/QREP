"""D3a corpus v0: the manifest, the annotations, the holdout rule and the fetch helpers.

Expected values are hand-computed in the comments beside each assertion; none comes from running
QREP. Record fragments and dimension strings are hand-written in the shapes the museum records
use; no saved third-party page is used. Every check that reads corpus/ reads the committed
files, so a row, an image or an annotation that breaks a rule fails here before corpus-guard runs.
"""

import hashlib
import io
import json
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

import corpus_fetch as cf
import corpus_screen as cs
from qrep.contract import OuterEdgeFrame, ReadRequest
from qrep_eval import annotation as an

# The same gate as tests/test_repo_guards.py: Pyodide has no git and no subprocesses, and the
# native jobs run these tests.
needs_git = pytest.mark.skipif(
    sys.platform == "emscripten" or shutil.which("git") is None,
    reason="needs a git executable and subprocesses",
)

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


# The v0 eval set, pinned photo by photo when the rule corpus/README.md records chose it
# (2026-10-11): every tier A photo, every tier R photo in on_point, curve, diamond_star or
# hexagon, and the first three tier R medallion and applique stems in sort order. A rule re-applied
# to a grown corpus would pick other photos, so membership is this list, and a later screen that
# adds photos changes it only by an edit here.
V0_EVAL_SET = frozenset({
    "lacma-30012", "lacma-44818", "lacma-52521", "lacma-52522", "lacma-54813", "lacma-54852",
    "lacma-54853", "lacma-54871", "lacma-54876", "lacma-54904", "lacma-56077", "lacma-58735",
    "lacma-59557", "lacma-60126", "lacma-60154", "lacma-61642", "lacma-63229", "lacma-63267",
    "met-13596", "met-13650", "met-13854", "met-13865", "met-13867", "met-13870", "met-13874",
    "met-13878", "met-13880", "met-13882", "met-13884", "met-13889", "met-13897", "met-13902",
    "met-13904", "met-13905", "met-13906", "met-13910", "met-13911", "met-13915", "met-16293",
    "met-16294", "met-229936", "met-717637", "met-717944", "met-814560", "met-854567",
    "met-854570", "smithsonian-chndm-1972-28-1", "smithsonian-chndm-1973-45-1",
    "smithsonian-chndm-1986-27-1", "smithsonian-nmah-556181", "smithsonian-nmah-556281",
    "smithsonian-nmah-556282", "smithsonian-nmah-556322", "smithsonian-nmah-556331",
    "smithsonian-saam-1987-80", "smithsonian-saam-1998-149-11", "smithsonian-saam-1998-149-12",
    "smithsonian-saam-1998-149-13", "smithsonian-saam-1998-149-14",
    "smithsonian-saam-1998-149-15", "smithsonian-saam-1998-149-17",
    "smithsonian-saam-1998-149-21", "smithsonian-saam-1998-149-23",
    "smithsonian-saam-1998-149-25", "smithsonian-saam-1998-149-26",
    "smithsonian-saam-1998-149-27", "smithsonian-saam-1998-149-3", "smithsonian-saam-1998-149-31",
    "smithsonian-saam-1998-8-3", "smithsonian-saam-2004-15-1", "smithsonian-saam-2004-15-2",
    "smithsonian-saam-2013-67-11", "smithsonian-saam-2013-67-16", "smithsonian-saam-2013-67-17",
    "smithsonian-saam-2013-67-2", "smithsonian-saam-2013-67-9", "smithsonian-saam-2016-57-2",
    "smithsonian-saam-2016-57-7", "smithsonian-saam-2017-24-1", "smithsonian-saam-2017-24-10",
    "smithsonian-saam-2017-24-11", "smithsonian-saam-2017-24-12", "smithsonian-saam-2017-24-13",
    "smithsonian-saam-2017-24-15", "smithsonian-saam-2017-24-27", "smithsonian-saam-2017-24-29",
    "smithsonian-saam-2017-24-3", "smithsonian-saam-2017-24-32", "smithsonian-saam-2017-24-34",
    "smithsonian-saam-2017-24-4", "smithsonian-saam-2017-24-5", "smithsonian-saam-2017-24-7",
    "smithsonian-saam-2021-67-2",
})


def test_the_eval_set_column_is_the_pinned_v0_set():
    # 13 tier A + 33 on_point + 15 curve + 16 diamond_star + 10 hexagon + 3 medallion + 3 applique
    # = 93 photos, the README's count.
    assert len(V0_EVAL_SET) == 13 + 33 + 15 + 16 + 10 + 3 + 3 == 93
    marked = {Path(row["file"]).stem for row in rows() if row["eval_set"] == "v0"}
    assert marked == V0_EVAL_SET


def test_the_rows_criterion_5_names_carry_their_tiers():
    # Source: plan D3a, criterion 5: the Smithsonian Double Irish Chain 2013.67.2 is an on-point
    # refusal, and the NMAH slide scans go to tier B; the in-scope slide scans are 556283, 556284
    # and 556288 (corpus/README.md).
    by_stem = {Path(row["file"]).stem: row for row in rows()}
    chain = by_stem["smithsonian-saam-2013-67-2"]
    assert (chain["tier"], chain["class"]) == ("R", "on_point")
    for stem in ("smithsonian-nmah-556283", "smithsonian-nmah-556284", "smithsonian-nmah-556288"):
        assert by_stem[stem]["tier"] == "B", stem


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


def test_readme_reports_each_tiers_photo_and_holdout_counts():
    # The README's v0 counts table gives each tier row's photo count in its Photos column and ends
    # the row with its holdout count; they must be the manifest's row count for that tier and the
    # pinned set's count, so a stale table fails here.
    by_stem = {Path(row["file"]).stem: row for row in rows()}
    expected = {
        tier: (sum(row["tier"] == tier for row in rows()),
               sum(by_stem[s]["tier"] == tier for s in HOLDOUT_V0))
        for tier in cf.TIERS
    }
    text = (CORPUS / "README.md").read_text(encoding="utf-8")
    reported = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] in cf.TIERS and cells[-1].isdigit() and cells[1].isdigit():
            reported[cells[0]] = (int(cells[1]), int(cells[-1]))
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
        "capture": [{"value": "museum_scan", "provenance": "screened"}],
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
    # Every x scales by 756 / 3873 and every y by 800 / 4096. By hand:
    # top left (30, 40): x = 22,680 / 3873; 3873 * 5 = 19,365, remainder 3,315, and
    # 3,315 / 3873 = 0.8559, so x = 5.8559; y = 32,000 / 4096 = 7.8125 (4096 * 7 = 28,672,
    # remainder 3,328, 3,328 / 4096 = 0.8125).
    # top right (3840, 35): x = 2,903,040 / 3873; 3873 * 749 = 2,900,877, remainder 2,163, and
    # 2,163 / 3873 = 0.5585, so x = 749.5585; y = 28,000 / 4096; 4096 * 6 = 24,576, remainder
    # 3,424, and 3,424 / 4096 = 0.8359375, so y = 6.8359375.
    # bottom right (3845, 4009): x = 2,906,820 / 3873; 3873 * 750 = 2,904,750, remainder 2,070,
    # and 2,070 / 3873 = 0.5345, so x = 750.5345; y = 3,207,200 / 4096; 4096 * 783 = 3,207,168,
    # remainder 32, and 32 / 4096 = 0.0078125, so y = 783.0078125.
    # bottom left (25, 4000): x = 18,900 / 3873; 3873 * 4 = 15,492, remainder 3,408, and
    # 3,408 / 3873 = 0.8799, so x = 4.8799; y = 3,200,000 / 4096; 4096 * 781 = 3,198,976,
    # remainder 1,024, and 1,024 / 4096 = 0.25, so y = 781.25.
    edge = {"kind": "outer_edge", "bands": [], "corners": {
        "top_left": {"x": 30, "y": 40}, "top_right": {"x": 3840, "y": 35},
        "bottom_right": {"x": 3845, "y": 4009}, "bottom_left": {"x": 25, "y": 4000}}}
    doc = sample(canvas=[3873, 4096],
                 frame=[{"value": {"outer_edge": edge}, "provenance": "verified-jake"}])
    corners = an.to_read_request(parse(doc), "copy.jpg", (756, 800)).frame.corners
    expected = {"top_left": (5.8559, 7.8125), "top_right": (749.5585, 6.8359375),
                "bottom_right": (750.5345, 783.0078125), "bottom_left": (4.8799, 781.25)}
    for name, (x, y) in expected.items():
        corner = getattr(corners, name)
        assert corner.x == pytest.approx(x, abs=1e-3), name
        assert corner.y == pytest.approx(y, abs=1e-3), name


def test_a_staged_size_must_keep_the_canvas_shape():
    # Canvas 3873 x 4096: 3873 / 4096 = 0.94556. A 756 x 800 copy: 756 / 800 = 0.945, a gap of
    # (0.94556 - 0.945) / 0.94556 = 0.06 percent, under 1 percent, so it scales. A swapped or
    # wrong size, 846 x 800: 846 / 800 = 1.0575, a gap of (1.0575 - 0.94556) / 0.94556 = 11.8
    # percent, over 1 percent, so it is refused.
    edge = {"kind": "outer_edge", "bands": [], "corners": {
        "top_left": {"x": 30, "y": 40}, "top_right": {"x": 3840, "y": 35},
        "bottom_right": {"x": 3845, "y": 4009}, "bottom_left": {"x": 25, "y": 4000}}}
    doc = parse(sample(canvas=[3873, 4096],
                       frame=[{"value": {"outer_edge": edge}, "provenance": "verified-jake"}]))
    assert isinstance(an.to_read_request(doc, "copy.jpg", (756, 800)), ReadRequest)
    with pytest.raises(ValueError, match="shape"):
        an.to_read_request(doc, "copy.jpg", (846, 800))


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


# A quad on the 1000 x 800 canvas, in order (120 < 880 across the top, 130 < 870 across the
# bottom, 70 < 720 down the left, 80 < 730 down the right) and convex: its four turns' cross
# products are 760 x 660 - 10 x 750 = 494,100, -10 x 640 + 650 x 750 = 481,100,
# 740 x 660 - 10 x 750 = 480,900 and 10 x 640 + 650 x 750 = 493,900, all positive.
PROPOSED_QUAD = [[120, 70], [880, 80], [870, 730], [130, 720]]


def test_a_stored_proposal_never_overrides_a_verified_derivation():
    # With prefer (verified-jake, proposed-a), the verified-jake frame (the only frame) ranks 0
    # and the proposed-a quad ranks 1; 1 is after 0, so the quad derives from the frame: OUTER's
    # corners, top left first, clockwise.
    doc = parse(sample(frame=[sample()["frame"][0]],
                       quad=[{"value": PROPOSED_QUAD, "provenance": "proposed-a"}]))
    view = an.sidecar_view(doc, prefer=("verified-jake", "proposed-a"))
    assert view["quad"] == [[100.0, 50.0], [900.0, 60.0], [890.0, 750.0], [110.0, 740.0]]
    # With the order turned, the proposed-a quad ranks 0, before the frame's 1, so it wins.
    view = an.sidecar_view(doc, prefer=("proposed-a", "verified-jake"))
    assert view["quad"] == [[120.0, 70.0], [880.0, 80.0], [870.0, 730.0], [130.0, 720.0]]


def test_a_stored_claim_stands_when_nothing_derives_its_field():
    # No frame derives a quad, so the proposed-a quad stands whatever its rank.
    doc = parse(sample(frame=[], quad=[{"value": PROPOSED_QUAD, "provenance": "proposed-a"}]))
    view = an.sidecar_view(doc, prefer=("verified-jake", "proposed-a"))
    assert view["quad"] == [[120.0, 70.0], [880.0, 80.0], [870.0, 730.0], [130.0, 720.0]]


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
        # A corner below the 1000 x 800 canvas (y = 801); the quad stays in order and convex
        # (bottom right (890, 801) is still below top right (900, 60) and right of bottom left
        # (110, 740)), so only the canvas refuses it.
        {"frame": [{"value": {"outer_edge": outer(bottom_right={"x": 890, "y": 801})},
                    "provenance": "proposed-b"}]},
        # A repeat of zero squares down and minus five across: each must be at least 1.
        {"repeat_cells": [{"value": [0, -5], "provenance": "proposed-a"}]},
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


def test_a_convex_clockwise_quad_with_rotated_labels_is_refused():
    # OUTER's corners moved one label on: top left (900, 60), top right (890, 750), bottom right
    # (110, 740), bottom left (100, 50). Traced in that order it is still convex and clockwise;
    # each turn's cross product (b - a) x (c - a) is positive:
    # (900,60)->(890,750)->(110,740): -10 x 680 - 690 x -790 = -6,800 + 545,100 = 538,300;
    # (890,750)->(110,740)->(100,50): -780 x -700 - -10 x -790 = 546,000 - 7,900 = 538,100;
    # (110,740)->(100,50)->(900,60): -10 x -680 - -690 x 790 = 6,800 + 545,100 = 551,900;
    # (100,50)->(900,60)->(890,750): 800 x 700 - 10 x 790 = 560,000 - 7,900 = 552,100.
    # Only the order check refuses it: top left x 900 is not left of top right x 890.
    rotated = outer(top_left={"x": 900, "y": 60}, top_right={"x": 890, "y": 750},
                    bottom_right={"x": 110, "y": 740}, bottom_left={"x": 100, "y": 50})
    with pytest.raises(ValidationError, match="out of order"):
        parse(sample(frame=[{"value": {"outer_edge": rotated}, "provenance": "proposed-b"}]))


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
    # The same with only the height off: a row of 1000 x 799 against the canvas's 800.
    other_height = {k: v | {"px_h": "799"} for k, v in licensed.items()}
    problems = an.licensed_photo_problems(parse(sample()), "met-1", other_height)
    assert len(problems) == 1 and "canvas" in problems[0]


def test_the_licensed_photo_rule_reads_a_gold_layout_by_its_identity_keys():
    # A D3b gold layout is its own format, named as D3b chooses: its photo and sha256 are read,
    # and its canvas when it names one, so extra keys pass and its file name is never compared
    # with the photo's stem (stem None).
    licensed = {"private/cache/met-1.jpg": {"license": "CC0-1.0", "sha256": SHA,
                                            "px_w": "1000", "px_h": "800"}}
    gold = {"photo": "private/cache/met-1.jpg", "sha256": SHA, "canvas": [1000, 800],
            "tiles": [{"row": 0, "col": 0, "fabric": 1}], "layout": {"rows": 30, "cols": 40}}
    assert an.licensed_photo_problems(gold, None, licensed) == []
    no_canvas = {k: v for k, v in gold.items() if k != "canvas"}
    assert an.licensed_photo_problems(no_canvas, None, licensed) == []
    # Each named key still binds: a canvas of 999 x 800 against the row's 1000 x 800, a missing
    # or other sha256, and a photo with no row are one problem each.
    empty_row = {k: v | {"sha256": ""} for k, v in licensed.items()}
    problems = an.licensed_photo_problems(no_canvas | {"sha256": ""}, None, empty_row)
    assert len(problems) == 1 and "another source" in problems[0]
    for bad, word in ((gold | {"canvas": [999, 800]}, "canvas"),
                      (gold | {"canvas": ["1000", "800"]}, "canvas"),
                      (no_canvas | {"sha256": "f" * 64}, "another source image"),
                      ({k: v for k, v in no_canvas.items() if k != "sha256"}, "another source"),
                      (no_canvas | {"photo": "local-photos/IMG_0001.png"}, "no row")):
        problems = an.licensed_photo_problems(bad, None, licensed)
        assert len(problems) == 1 and word in problems[0], problems


def test_every_committed_annotation_names_a_licensed_photo():
    # The issue #113 rule, applied by this test until corpus-guard enforces it: every committed
    # annotation or gold JSON, in any subfolder, names a photo with a CC0-1.0 or PDM-1.0 row whose
    # sha256 matches, and whose canvas matches wherever the file names one (an annotation always
    # does); an annotation sits under the photo's own stem. Gold files are read
    # as plain JSON under any name, because D3b's gold layouts are not annotations.
    by_file = {row["file"]: row for row in rows()}
    assert ANNOTATIONS
    docs = [(path, an.load(path), path.stem) for path in ANNOTATIONS] + [
        (path, json.loads(path.read_text(encoding="utf-8")), None) for path in GOLD]
    for path, doc, stem in docs:
        problems = an.licensed_photo_problems(doc, stem, by_file)
        assert problems == [], (path.name, problems)


def test_capture_and_device_class_are_the_screens_calls():
    # No museum record states how its photo was captured or on what device: the screen sets both
    # from the source (a museum photo is a museum scan on a museum's equipment), so both carry
    # the screen's code, and source-record marks only values copied from the record.
    for path in ANNOTATIONS:
        doc = an.load(path)
        for name in ("capture", "device_class"):
            # A later verified claim may sit beside the screen's, which stays.
            codes = {c.provenance for c in getattr(doc, name)}
            assert "screened" in codes and "source-record" not in codes, (path.name, name)
        for name in an.CLAIM_FIELDS:
            if name != "finished_size":
                codes = {c.provenance for c in getattr(doc, name)}
                assert "source-record" not in codes, (path.name, name)


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


def test_every_annotation_carries_its_rows_finished_size():
    # The review of 2d06464 found an annotation with no finished size although its record gave
    # one; an annotation whose row has a finished_in carries it as a source-record claim.
    by_file = {row["file"]: row for row in rows()}
    for path in ANNOTATIONS:
        doc = an.load(path)
        copied = [c for c in doc.finished_size if c.provenance == "source-record"]
        assert len(copied) == (1 if by_file[doc.photo]["finished_in"] else 0), path.name


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
        # One label alone wins too. A width first: 70 in wide, so the other, 80 in, is the height.
        ("W. 70 x 80 in.", (70.0, 80.0)),
        # A height second: 80 in high, so the first, 70 in, is the width.
        ("70 x H. 80 in.", (70.0, 80.0)),
        # A height first: 80 in high, so the second, 70 in, is the width.
        ("H. 80 x 70 in.", (70.0, 80.0)),
        # A width second: 70 in wide, so the first, 80 in, is the height.
        ("80 x W. 70 in.", (70.0, 80.0)),
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
        # A mounted object: the size without the mount wins over the mounted size that comes
        # first. 45 in high; 36 5/8 = 36.625 in wide, an exact half at the third place, which
        # rounds to the even digit: 36.62.
        ("H x W x D (with mount): 48 1/2 × 39 1/2 × 1 1/2 in. (123.2 × 100.3 × "
         "3.8 cm); H x W (without mount): 45 × 36 5/8 in. (114.3 × 93 cm)",
         (36.62, 45.0)),
        # A framed object, frame first: the sight size is the object's. 18 1/4 = 18.25 in high,
        # 36 1/4 = 36.25 in wide.
        ("Frame: 21 x 39 in.; sight: 18 1/4 x 36 1/4 in.", (36.25, 18.25)),
        # The frame after the sight size, with no semicolon between them: still the sight size.
        ("sight 18 1/4 x 36 1/4 in. (47.0 x 92.0 cm) irregular frame: 21 x 39 x 1 1/4 in. "
         "(53.4 x 99.1 x 3.1 cm)", (36.25, 18.25)),
        # Only a framed size: it is all the text gives, so it stands. 21 in high, 39 in wide.
        ("framed: 21 x 39 in.", (39.0, 21.0)),
        # The centimetre restatement shares the framed size's status, so inches still win:
        # 21 in high, 39 in wide, not 53.3 / 2.54 = 20.98 and 99.1 / 2.54 = 39.02.
        ("framed: 21 x 39 in. (53.3 x 99.1 cm)", (39.0, 21.0)),
        # The NMAH shape restates after a semicolon: 40 in high, 30 in wide, not the cm pair.
        ("framed: 40 in x 30 in; 101 cm x 76 cm", (30.0, 40.0)),
        # "without canvas mount" is the object's own size: 56 1/2 = 56.5 in high,
        # 69 1/2 = 69.5 in wide.
        ("H x W ((a) without canvas mount): 56 1/2 x 69 1/2 in.; H x W (with canvas mount): "
         "60 x 73 in.", (69.5, 56.5)),
        # A mount named in an earlier sentence does not qualify the next one's size:
        # 80 in high, 70 in wide.
        ("Quilt mounted on linen. Overall: 80 x 70 in.; Linen backing: 84 x 74 in.",
         (70.0, 80.0)),
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
        # A decade range with a two-digit end: the 30s after 1920s are 1930 to 1930 + 9 = 1939.
        ("1920s-30s", 1939),
        # A slash writes a range: 1929/30 ends in 19 + 30 = 1930.
        ("1929/30", 1930),
        # A "00s" decade is also how a century is written, so 1900s reads the century's last
        # year, 1900 + 99 = 1999, erring toward the modern skip.
        ("1900s", 1999),
        # A two-digit end below the start's last two digits (05 < 95) crosses into the next
        # century: (18 + 1) x 100 + 5 = 1905.
        ("1895-05", 1905),
        # A curly apostrophe reads as a straight one: 1920 + 9 = 1929.
        ("1920\u2019s", 1929),
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


def test_a_smithsonian_row_reads_its_measurements_label():
    # NMAH records label their size "Measurements" rather than "Dimensions", and list materials
    # under "Physical Description", which is no size. By hand: the pair 84 in x 50 in carries no
    # H or W label, so it reads height x width: 50 in wide, 84 in high.
    row = json.loads(json.dumps(SI_ROW))
    row["content"]["freetext"]["physicalDescription"] = [
        {"label": "Physical Description", "content": "fabric, cotton (overall material)"},
        {"label": "Measurements", "content": "overall: 84 in x 50 in; 213 cm x 126 cm"},
    ]
    c = cf.si_candidate(row)
    assert c.dimensions_text == "overall: 84 in x 50 in; 213 cm x 126 cm"
    assert cf.parse_finished_size(c.dimensions_text) == (50.0, 84.0)


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
    # two problems: the row's flag is not the one SOURCES sets for the Met, and the row no longer
    # states what the record says.
    problems = cf.recheck(FakeClient(pages(MET_RECORD)),
                          [met_row(rights_flag="isPublicDomain=yes")], tmp_path)
    assert problems == [
        "private/cache/met-11.jpg: rights_flag isPublicDomain=yes is not isPublicDomain=true, "
        "the rights_flag met sets",
        "private/cache/met-11.jpg: rights flag changed from isPublicDomain=yes "
        "to isPublicDomain=true",
    ]


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
    # Two Met rows cite one policy page, so it is requested once.
    both = [met_row(), met_row(file="private/cache/met-12.jpg", object_id="12")]
    client = FakeClient(pages(MET_RECORD) | {
        f"{cf.MET}/v1/objects/12": MET_RECORD | {"objectID": 12}})
    assert cf.recheck(client, both, tmp_path) == []
    assert [url for url, _ in client.sent].count(MET_POLICY) == 1


def test_the_recheck_reads_the_policy_url_the_row_cites_and_reports_its_drift(tmp_path):
    # The row cites a policy URL that is not the Met's in SOURCES: the recheck requests the row's
    # URL, never the constant, and reports that the row's policy_url differs from the source's.
    moved = "https://www.metmuseum.org/policies/image-resources"
    client = FakeClient({MET_OBJECT: MET_RECORD, moved: b"policy page"})
    problems = cf.recheck(client, [met_row(policy_url=moved)], tmp_path)
    requested = [url for url, _ in client.sent]
    assert moved in requested and MET_POLICY not in requested
    assert problems == [f"private/cache/met-11.jpg: policy_url {moved} is not {MET_POLICY}, "
                        "the policy_url met sets"]


SI_SEARCH = f"{cf.SI_API}/search?" + cf._query(
    {"q": cf.SI_QUERY, "rows": "1000", "start": "0", "api_key": cf.SI_DEMO_KEY})
SI_IMAGE = "https://ids.si.edu/ids/download?id=NMAH-1.jpg"


def si_row(**changes) -> dict[str, str]:
    license, flag, policy = SOURCE_TERMS["smithsonian"]
    return {"file": "private/cache/smithsonian-nmah-1.jpg", "source": "smithsonian",
            "object_id": "nmah_1", "license": license, "rights_flag": flag,
            "policy_url": policy, "image_url": SI_IMAGE} | changes


def two_media() -> dict:
    """SI_ROW whose own medium (NMAH-1, the row's image) is restricted, beside a second image
    medium (NMAH-2) that is CC0."""
    record = json.loads(json.dumps(SI_ROW))
    media = record["content"]["descriptiveNonRepeating"]["online_media"]["media"]
    media[0]["usage"]["access"] = "Usage conditions apply"
    media.append({"type": "Images", "usage": {"access": "CC0"},
                  "content": "https://ids.si.edu/ids/deliveryService?id=NMAH-2",
                  "resources": [{"label": "High-resolution JPEG",
                                 "url": "https://ids.si.edu/ids/download?id=NMAH-2.jpg"}]})
    return record


def test_the_recheck_reports_a_smithsonian_row_with_no_live_record(tmp_path):
    # The search answers with nmah_1 only, so the row for nmah_2 has no live record: one problem,
    # and the Smithsonian policy page answers 200.
    client = FakeClient({SI_SEARCH: {"response": {"rows": [SI_ROW]}},
                         SOURCE_TERMS["smithsonian"][2]: b"policy page"})
    row = si_row(file="private/cache/smithsonian-nmah-2.jpg", object_id="nmah_2")
    problems = cf.recheck(client, [row], tmp_path)
    assert problems == ["private/cache/smithsonian-nmah-2.jpg: no live record (withdrawn, or no "
                        "longer flagged)"]


def test_the_recheck_reads_the_medium_that_serves_the_rows_image(tmp_path):
    # The record still holds a CC0 medium, but the row's image is NMAH-1, now restricted, so the
    # live flag renders media.usage.access=Usage conditions apply against the row's CC0.
    client = FakeClient({SI_SEARCH: {"response": {"rows": [two_media()]}},
                         SOURCE_TERMS["smithsonian"][2]: b"policy page"})
    problems = cf.recheck(client, [si_row()], tmp_path)
    assert problems == ["private/cache/smithsonian-nmah-1.jpg: rights flag changed from "
                        "media.usage.access=CC0 to media.usage.access=Usage conditions apply"]


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


def test_a_smithsonian_live_flag_reads_the_medium_of_the_rows_image():
    # two_media(): NMAH-1 is restricted, NMAH-2 is CC0. The row's image matches NMAH-1 by its
    # resource URL or by its delivery URL (content), so either reads the restricted value.
    record = two_media()
    restricted = "media.usage.access=Usage conditions apply"
    assert cf.live_flag("smithsonian", record, SI_IMAGE) == restricted
    assert cf.live_flag("smithsonian", record,
                        "https://ids.si.edu/ids/deliveryService?id=NMAH-1") == restricted
    # No medium serves the URL, or no URL is given: any CC0 image medium reads CC0, as
    # si_candidate clears a record.
    assert cf.live_flag("smithsonian", record, "https://ids.si.edu/ids/download?id=X.jpg") == (
        "media.usage.access=CC0")
    assert cf.live_flag("smithsonian", record) == "media.usage.access=CC0"


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
    # not screened again and stays; lacma 2048 is new and is added: three rows. Neither new row
    # names an eval_set: met 11 keeps its old row's "v0", and lacma 2048, a new photo, gets "".
    old = [{"source": "met", "object_id": "11", "tier": "B", "eval_set": "v0"},
           {"source": "aic", "object_id": "22", "tier": "A", "eval_set": ""}]
    new = [{"source": "met", "object_id": "11", "tier": "A"},
           {"source": "lacma", "object_id": "2048", "tier": "R"}]
    merged = sorted(cf.merge_rows(old, new), key=lambda r: (r["source"], r["object_id"]))
    assert merged == [{"source": "aic", "object_id": "22", "tier": "A", "eval_set": ""},
                      {"source": "lacma", "object_id": "2048", "tier": "R", "eval_set": ""},
                      {"source": "met", "object_id": "11", "tier": "A", "eval_set": "v0"}]


def test_a_rescreen_without_an_eval_set_column_keeps_the_old_eval_set(tmp_path):
    # A fetched met 11 (80 x 72 in., 1000 x 800 px) whose old row is in the v0 eval set.
    cf.save_candidates(tmp_path, [cf.Candidate(
        "met", "11", "Quilt", "https://www.metmuseum.org/art/collection/search/11",
        "https://images.metmuseum.org/x.jpg", "Gift", "80 x 72 in.", 1850,
        sha256="a" * 64, px_w=1000, px_h=800)])
    old = [{"source": "met", "object_id": "11", "tier": "B", "eval_set": "v0"}]
    # A four-column decision says nothing about the eval set: build_rows leaves it None, and the
    # merge keeps the old row's v0.
    four = tmp_path / "four.csv"
    four.write_text("stem,tier,class,commit_ok\nmet-11,A,squares,no\n", encoding="utf-8")
    (built,) = cf.build_rows(tmp_path, four, {})
    assert built["eval_set"] is None
    (merged,) = cf.merge_rows(old, [built])
    assert (merged["tier"], merged["eval_set"]) == ("A", "v0")
    # A five-column decision with an empty eval_set says the photo leaves the set: "".
    five = tmp_path / "five.csv"
    five.write_text("stem,tier,class,commit_ok,eval_set\nmet-11,A,squares,no,\n",
                    encoding="utf-8")
    (merged,) = cf.merge_rows(old, cf.build_rows(tmp_path, five, {}))
    assert merged["eval_set"] == ""


def test_only_a_cleared_row_that_may_be_committed_licenses_a_copy(tmp_path):
    # A committed copy needs a row for its source bytes, licensed CC0-1.0 or PDM-1.0, with
    # commit_ok yes; each change below breaks one of the three.
    src = tmp_path / "x.jpg"
    Image.new("RGB", (1000, 500), "white").save(src)
    row = {"sha256": sha256_file(src), "license": "CC0-1.0", "commit_ok": "yes"}
    assert cs.committable_row(src, [row]) == row
    assert cs.committable_row(src, [row | {"license": "PDM-1.0"}])["license"] == "PDM-1.0"
    for change in ({"commit_ok": "no"}, {"license": "CC-BY-4.0"}, {"sha256": "0" * 64}):
        with pytest.raises(cs.NotCommittable):
            cs.committable_row(src, [row | change])


def test_the_downsize_command_checks_its_input_before_it_writes(tmp_path, monkeypatch):
    # The command's own call path: a source whose bytes match no manifest row is refused, and
    # nothing reaches the images folder.
    monkeypatch.setattr(cs, "IMAGES", tmp_path / "images")
    src = tmp_path / "x.jpg"
    Image.new("RGB", (1000, 500), "white").save(src)
    out = tmp_path / "images" / "x.jpg"
    with pytest.raises(SystemExit, match="no manifest row"):
        cs.main(["downsize", str(src), str(out)])
    assert not out.exists()
    with pytest.raises(SystemExit, match="cannot be read"):
        cs.main(["downsize", str(tmp_path / "missing.jpg"), str(out)])
    # With a cleared row for the source, the copy must take the row's cache name, met-1.jpg.
    row = {"sha256": sha256_file(src), "license": "CC0-1.0", "commit_ok": "yes",
           "source": "met", "object_id": "1"}
    monkeypatch.setattr(cs, "read_manifest", lambda: [row])
    with pytest.raises(SystemExit, match="met-1.jpg"):
        cs.main(["downsize", str(src), str(tmp_path / "images" / "met-2.jpg")])
    assert cs.main(["downsize", str(src), str(tmp_path / "images" / "met-1.jpg")]) == 0
    assert sorted(p.name for p in (tmp_path / "images").iterdir()) == ["met-1.jpg"]


def test_a_committed_copy_carries_no_jpeg_comment(tmp_path):
    src = tmp_path / "x.jpg"
    Image.new("RGB", (1000, 500), "white").save(src, comment=b"accession 1985.1")
    with Image.open(src) as image:
        assert image.info.get("comment") == b"accession 1985.1"
    out = tmp_path / "y.jpg"
    _, width, height = cs.downsize(src, out)
    # By hand: 1000 x 500 fits 800 x 800 at a scale of 800 / 1000 = 0.8, so 800 x 400.
    assert (width, height) == (800, 400)
    with Image.open(out) as image:
        assert "comment" not in image.info
    assert b"accession" not in out.read_bytes()


@needs_git
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
