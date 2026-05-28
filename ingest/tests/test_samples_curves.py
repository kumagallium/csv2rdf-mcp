"""Phase 1 samples + curves ingester tests."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, XSD

from csv2rdf.starrydata import (
    DEFAULT_ONTOLOGY,
    DEFAULT_RESOURCE,
    IngestConfig,
    ingest_curves,
    ingest_samples,
    parse_float_array,
    parse_sample_info,
)

SD = Namespace(DEFAULT_ONTOLOGY)
SDR = Namespace(DEFAULT_RESOURCE)
SCHEMA = Namespace("https://schema.org/")


# ----------------------------------------------------------------------------
# Pure helpers
# ----------------------------------------------------------------------------


def test_parse_sample_info_strips_empty_entries() -> None:
    raw = json.dumps(
        {
            "MaterialFamily": {"category": "Bi2Te3", "comment": "", "extracted": ""},
            "GrainSize": {"category": "", "comment": "", "extracted": ""},
            "Form": {"category": "Film", "comment": "thin film"},
        }
    )
    out = parse_sample_info(raw)
    assert "MaterialFamily" in out
    assert "Form" in out
    assert "GrainSize" not in out, "全フィールド空のエントリは除外する"
    assert out["MaterialFamily"]["category"] == "Bi2Te3"
    assert out["Form"]["comment"] == "thin film"


def test_parse_sample_info_invalid_returns_empty() -> None:
    assert parse_sample_info("") == {}
    assert parse_sample_info("not-json") == {}
    assert parse_sample_info("[]") == {}


def test_parse_float_array_basic() -> None:
    assert parse_float_array("[1.5, 2.0, 3.25]") == [1.5, 2.0, 3.25]


def test_parse_float_array_handles_garbage() -> None:
    # 数値でないもの, None, NaN を取り除く
    assert parse_float_array('[1, "x", null, 2]') == [1.0, 2.0]
    assert parse_float_array("[]") == []
    assert parse_float_array("bad") == []
    assert parse_float_array("") == []


# ----------------------------------------------------------------------------
# samples ingester
# ----------------------------------------------------------------------------


@pytest.fixture
def samples_csv(tmp_path: Path) -> Path:
    rows = [
        {
            "sample_name": '"PH1000"',
            "sample_id": "16786",
            "composition": '"PEDOT:PSS with DMSO"',
            "composition_details": '"Bi2Te3 ball-milled into PEDOT:PSS"',
            "SID": "2",  # → paper/2
            "DOI": "10.1021/am100654p",
            "created_at": "Wed May 29 2019",
            "updated_at": "Wed May 29 2019",
            "sample_info": json.dumps(
                {
                    "MaterialFamily": {"category": "Bi2Te3", "comment": ""},
                    "GrainSize": {"category": "", "comment": "", "extracted": ""},
                    "Form": {"category": "Film", "comment": "thin film"},
                }
            ),
        },
        {
            "sample_name": '"Cu2.025Cd0.975SnSe4"',
            "sample_id": "6027",
            "composition": '"Pb1Te1.01Na0.02"',
            "composition_details": "",
            "SID": "1",
            "DOI": "10.1021/ar400290f",
            "created_at": "",
            "updated_at": "",
            "sample_info": "{}",
        },
    ]
    p = tmp_path / "samples.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return p


def _load(path: Path) -> Graph:
    g = Graph()
    g.parse(str(path), format="turtle")
    return g


def test_ingest_samples_emits_basic_triples(samples_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "samples.ttl"
    stats = ingest_samples(samples_csv, out, IngestConfig(emit_prov=False))
    assert stats.rows_in == 2
    assert stats.rows_ok == 2
    assert stats.rows_err == 0
    g = _load(out)
    s16786 = URIRef(DEFAULT_RESOURCE + "sample/16786")
    assert (s16786, RDF.type, SD.Sample) in g
    assert (s16786, RDF.type, PROV.Entity) in g
    assert (s16786, DCTERMS.identifier, Literal("16786")) in g
    assert (s16786, SCHEMA.name, Literal("PH1000")) in g
    assert (s16786, SD.compositionString, Literal("PEDOT:PSS with DMSO")) in g
    # fromPaper link
    assert (s16786, SD.fromPaper, URIRef(DEFAULT_RESOURCE + "paper/2")) in g


def test_samples_have_no_bnodes(samples_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "samples.ttl"
    ingest_samples(samples_csv, out, IngestConfig(emit_prov=False))
    g = _load(out)
    bnodes = [s for s in g.subjects() if isinstance(s, BNode)] + [
        o for o in g.objects() if isinstance(o, BNode)
    ]
    assert bnodes == []


def test_samples_descriptor_iris(samples_csv: Path, tmp_path: Path) -> None:
    """sample_info の descriptor は sdr:descriptor/{sid}/{idx} の IRI を持つ"""
    out = tmp_path / "samples.ttl"
    ingest_samples(samples_csv, out, IngestConfig(emit_prov=False))
    g = _load(out)
    s = URIRef(DEFAULT_RESOURCE + "sample/16786")
    descriptors = list(g.objects(s, SD.hasDescriptor))
    assert len(descriptors) == 2  # MaterialFamily, Form (GrainSize は除外)
    assert all(str(d).startswith(DEFAULT_RESOURCE + "descriptor/16786/") for d in descriptors)
    # descriptor 内容の検証
    names = {str(o) for d in descriptors for o in g.objects(d, SD.descriptorName)}
    assert names == {"MaterialFamily", "Form"}


# ----------------------------------------------------------------------------
# curves ingester
# ----------------------------------------------------------------------------


@pytest.fixture
def curves_csv(tmp_path: Path) -> Path:
    rows = [
        {
            "SID": "6",
            "DOI": "10.1021/am405410e",
            "composition": '"Pb1.00025Zn0.02Te1.02I0.0005"',
            "sample_id": "113",
            "figure_id": "79",
            "figure_name": '"6(b)"',
            "prop_x": '"Temperature"',
            "prop_y": '"Seebeck coefficient"',
            "unit_x": '"K"',
            "unit_y": '"V*K^(-1)"',
            "x": "[300, 400, 500, 600, 650]",
            "y": "[-0.0001, -0.0002, -0.0003, -0.0004, -0.00035]",
            "created_at": "",
            "updated_at": "",
            "project_names": '["ThermoelectricMaterials"]',
            "comments": '"figure (b)"',
        },
        {
            # Empty x/y to verify graceful handling
            "SID": "7",
            "DOI": "",
            "composition": '"Bi2Te3"',
            "sample_id": "114",
            "figure_id": "80",
            "figure_name": '"7"',
            "prop_x": '"Temperature"',
            "prop_y": '"Resistivity"',
            "unit_x": '"K"',
            "unit_y": '"ohm*cm"',
            "x": "",
            "y": "",
            "created_at": "",
            "updated_at": "",
            "project_names": "[]",
            "comments": "",
        },
    ]
    p = tmp_path / "curves.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return p


def test_ingest_curves_emits_basic_triples(curves_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "curves.ttl"
    stats = ingest_curves(curves_csv, out, IngestConfig(emit_prov=False))
    assert stats.rows_in == 2
    assert stats.rows_ok == 2
    g = _load(out)
    c79 = URIRef(DEFAULT_RESOURCE + "curve/79")
    assert (c79, RDF.type, SD.Curve) in g
    assert (c79, RDF.type, PROV.Entity) in g
    assert (c79, SD.figureName, Literal("6(b)")) in g
    assert (c79, SD.ofSample, URIRef(DEFAULT_RESOURCE + "sample/113")) in g
    assert (c79, SD.propertyX, Literal("Temperature")) in g
    assert (c79, SD.propertyY, Literal("Seebeck coefficient")) in g
    assert (c79, SD.unitXString, Literal("K")) in g
    assert (c79, SD.unitYString, Literal("V*K^(-1)")) in g


def test_curves_aggregates(curves_csv: Path, tmp_path: Path) -> None:
    """設計プラン §4 方針 C: x/y 集約値 (Min/Max/PointCount) を出す"""
    out = tmp_path / "curves.ttl"
    ingest_curves(curves_csv, out, IngestConfig(emit_prov=False))
    g = _load(out)
    c79 = URIRef(DEFAULT_RESOURCE + "curve/79")
    x_min = list(g.objects(c79, SD.xMin))
    x_max = list(g.objects(c79, SD.xMax))
    y_min = list(g.objects(c79, SD.yMin))
    y_max = list(g.objects(c79, SD.yMax))
    point_count = list(g.objects(c79, SD.pointCount))
    assert len(x_min) == 1 and float(x_min[0]) == 300.0
    assert len(x_max) == 1 and float(x_max[0]) == 650.0
    # Y min/max: with negatives, min = -0.0004, max = -0.0001
    assert len(y_min) == 1 and float(y_min[0]) == pytest.approx(-0.0004)
    assert len(y_max) == 1 and float(y_max[0]) == pytest.approx(-0.0001)
    assert len(point_count) == 1 and int(point_count[0]) == 5
    # xsd:double / xsd:integer のデータ型確認
    assert x_min[0].datatype == XSD.double
    assert point_count[0].datatype == XSD.integer


def test_curves_keep_json_literal(curves_csv: Path, tmp_path: Path) -> None:
    """生 JSON 配列は xsd:string literal として保持する (方針 C)"""
    out = tmp_path / "curves.ttl"
    ingest_curves(curves_csv, out, IngestConfig(emit_prov=False))
    g = _load(out)
    c79 = URIRef(DEFAULT_RESOURCE + "curve/79")
    x_vals = list(g.objects(c79, SD.xValuesJSON))
    y_vals = list(g.objects(c79, SD.yValuesJSON))
    assert len(x_vals) == 1
    assert "300" in str(x_vals[0]) and "650" in str(x_vals[0])
    assert len(y_vals) == 1
    assert "-0.0004" in str(y_vals[0])


def test_curves_empty_xy_no_aggregates(curves_csv: Path, tmp_path: Path) -> None:
    """x/y が空の curve は集約値を出さない (Curve 自体は生成)"""
    out = tmp_path / "curves.ttl"
    ingest_curves(curves_csv, out, IngestConfig(emit_prov=False))
    g = _load(out)
    c80 = URIRef(DEFAULT_RESOURCE + "curve/80")
    assert (c80, RDF.type, SD.Curve) in g
    assert list(g.objects(c80, SD.xMin)) == []
    assert list(g.objects(c80, SD.pointCount)) == []


def test_curves_have_no_bnodes(curves_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "curves.ttl"
    ingest_curves(curves_csv, out, IngestConfig(emit_prov=False))
    g = _load(out)
    bnodes = [s for s in g.subjects() if isinstance(s, BNode)] + [
        o for o in g.objects() if isinstance(o, BNode)
    ]
    assert bnodes == []
