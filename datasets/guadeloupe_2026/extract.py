"""
Extract Guadeloupe 2026 movement data from official PDFs.
No regulatory rules invented — data only.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

ATTACHMENTS = Path("/home/workdir/attachments")
OUT = Path("/home/workdir/artifacts/movement_engine/datasets/guadeloupe_2026")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _clean(s: Optional[str]) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


def extract_posts_precis(pdf_path: Path) -> List[Dict[str, Any]]:
    """VOEUX PRECIS — one row per post/support line."""
    posts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table in tables:
                if not table or len(table) < 2:
                    continue
                header = [_clean(c).lower() for c in table[0]]
                # detect header row
                if not any("poste" in h or "commune" in h or "nature" in h for h in header):
                    # try first data-looking rows
                    pass
                for row in table[1:]:
                    if not row or all(c is None or str(c).strip() == "" for c in row):
                        continue
                    cells = [_clean(c) for c in row]
                    # expected columns from document analysis:
                    # 0 Numéro du poste, 1 Commune, 2 Circonscription, 3 Établissement,
                    # 4 Nature, 5 Spécialité, 6 Nb.Cl., 7 Dont Cl.Spé.,
                    # 8 Supports à profil, 9 Nb supports, 10 Dont vacants
                    if len(cells) < 5:
                        continue
                    post_id = cells[0]
                    if not post_id or not re.match(r"^\d+$", post_id):
                        continue
                    try:
                        nb_supports = int(cells[9]) if len(cells) > 9 and cells[9].isdigit() else 1
                    except Exception:
                        nb_supports = 1
                    try:
                        nb_vacants = int(cells[10]) if len(cells) > 10 and cells[10].isdigit() else 0
                    except Exception:
                        nb_vacants = 0
                    nature_raw = cells[4] if len(cells) > 4 else ""
                    nature_code = nature_raw.split(" - ")[0].strip() if " - " in nature_raw else nature_raw
                    posts.append({
                        "id": post_id,
                        "commune": cells[1] if len(cells) > 1 else "",
                        "circonscription": cells[2] if len(cells) > 2 else "",
                        "etablissement": cells[3] if len(cells) > 3 else "",
                        "nature": nature_raw,
                        "nature_code": nature_code,
                        "specialite": cells[5] if len(cells) > 5 else "",
                        "nb_classes": cells[6] if len(cells) > 6 else "",
                        "nb_classes_spe": cells[7] if len(cells) > 7 else "",
                        "profil": cells[8] if len(cells) > 8 else "",
                        "capacity": nb_supports,
                        "vacants": nb_vacants,
                        "source_page": page_num,
                        "source_doc": "VOEUX_PRECIS",
                    })
    return posts


def extract_groups_generic(pdf_path: Path, source_doc: str) -> List[Dict[str, Any]]:
    """Generic group extractor for ASSIMILES / MOB / ZONE PDFs."""
    groups = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table in tables:
                if not table or len(table) < 2:
                    continue
                for row in table[1:]:
                    if not row:
                        continue
                    cells = [_clean(c) for c in row]
                    if not cells[0] or not re.match(r"^\d+$", cells[0]):
                        # also accept alphanumeric codes as first col sometimes
                        if not cells[0]:
                            continue
                    group_id = cells[0]
                    # flexible column mapping
                    code = cells[1] if len(cells) > 1 else ""
                    categorie = cells[2] if len(cells) > 2 else ""
                    typ = cells[3] if len(cells) > 3 else ""
                    libelle = cells[4] if len(cells) > 4 else ""
                    # last numeric-looking cell often = nb postes
                    nb_postes = None
                    mobilite_obligatoire = None
                    for c in reversed(cells):
                        if c.isdigit():
                            nb_postes = int(c)
                            break
                    for c in cells:
                        cl = c.lower()
                        if cl in ("oui", "non"):
                            mobilite_obligatoire = cl == "oui"
                            break
                    groups.append({
                        "id": group_id,
                        "code": code,
                        "categorie": categorie,
                        "type": typ,
                        "libelle": libelle,
                        "nb_postes": nb_postes,
                        "mobilite_obligatoire": mobilite_obligatoire,
                        "source_page": page_num,
                        "source_doc": source_doc,
                        "composition_posts": None,  # UNKNOWN without cross-ref
                        "selection_rule_inside_group": "UNKNOWN",
                        "eligibility_rule": "UNKNOWN",
                    })
    return groups


def build_dataset() -> Dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    raw_dir = OUT / "raw"
    raw_dir.mkdir(exist_ok=True)

    sources = {
        "VOEUX_PRECIS": ATTACHMENTS / "VOEUX PRECIS_2.pdf",
        "ASSIMILES_COMMUNES": ATTACHMENTS / "VOEUX GROUPE ASSIMILES COMMUNES_0.pdf",
        "AUTRE_MOB": ATTACHMENTS / "VOEUX GROUPE AUTRE MOB_2.pdf",
        "AUTRE_ZONE": ATTACHMENTS / "VOEUX GROUPE AUTRE ZONE.pdf",
    }

    manifest_sources = {}
    for key, path in sources.items():
        if not path.exists():
            raise FileNotFoundError(path)
        manifest_sources[key] = {
            "path": str(path),
            "filename": path.name,
            "sha256": file_sha256(path),
            "size_bytes": path.stat().st_size,
        }

    print("Extracting posts (VOEUX PRECIS)...")
    posts = extract_posts_precis(sources["VOEUX_PRECIS"])
    print(f"  posts: {len(posts)}")

    print("Extracting groups ASSIMILES COMMUNES...")
    groups_assimil = extract_groups_generic(sources["ASSIMILES_COMMUNES"], "ASSIMILES_COMMUNES")
    print(f"  groups assimilés: {len(groups_assimil)}")

    print("Extracting groups AUTRE MOB...")
    groups_mob = extract_groups_generic(sources["AUTRE_MOB"], "AUTRE_MOB")
    print(f"  groups MOB: {len(groups_mob)}")

    print("Extracting groups AUTRE ZONE...")
    groups_zone = extract_groups_generic(sources["AUTRE_ZONE"], "AUTRE_ZONE")
    print(f"  groups ZONE: {len(groups_zone)}")

    # dedupe groups by id keeping first
    all_groups = {}
    for g in groups_assimil + groups_mob + groups_zone:
        gid = g["id"]
        if gid not in all_groups:
            all_groups[gid] = g
        else:
            # merge flags
            if g.get("mobilite_obligatoire") is not None:
                all_groups[gid]["mobilite_obligatoire"] = g["mobilite_obligatoire"]

    posts_path = OUT / "posts.json"
    groups_path = OUT / "groups.json"
    validation = {
        "posts_count": len(posts),
        "groups_count": len(all_groups),
        "posts_with_vacants": sum(1 for p in posts if p.get("vacants", 0) > 0),
        "total_capacity": sum(p.get("capacity", 1) for p in posts),
        "total_vacants": sum(p.get("vacants", 0) for p in posts),
        "nature_codes": sorted({p.get("nature_code", "") for p in posts if p.get("nature_code")}),
        "group_types": sorted({g.get("type", "") for g in all_groups.values()}),
        "warnings": [
            "composition_posts for groups is UNKNOWN — no post-level membership in source PDFs",
            "selection_rule_inside_group is UNKNOWN",
            "eligibility_rule for groups is UNKNOWN",
            "no agent wishes in source PDFs — synthetic wishes required for Alpha",
        ],
    }

    posts_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    groups_path.write_text(
        json.dumps(list(all_groups.values()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT / "validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest = {
        "dataset_id": "guadeloupe-2026-alpha",
        "version": "2026.08.11-alpha1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources": manifest_sources,
        "files": {
            "posts.json": {"sha256": file_sha256(posts_path), "count": len(posts)},
            "groups.json": {"sha256": file_sha256(groups_path), "count": len(all_groups)},
        },
        "scope": "INTRA_DEPARTEMENTAL_1D_GUADELOUPE_2026",
        "notes": [
            "Data extracted from official movement PDFs",
            "No regulatory scoring rules derived from these files",
            "Group internal selection rules marked UNKNOWN",
            "Agent wishes not present — must be synthetic for Alpha",
        ],
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Done.")
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return {"manifest": manifest, "validation": validation}


if __name__ == "__main__":
    build_dataset()
