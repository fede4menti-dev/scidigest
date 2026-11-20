"""Research topics readers can follow. The iPhone app mirrors these ids in Taxonomy.swift
(a test checks they match). Ids are stable; names can change."""
from __future__ import annotations

GROUPS = [
    ("physical", "Physical Sciences, Math & Computing", [
        ("physics", "Physics",
         "classical mechanics, quantum science, optics and photonics, condensed matter, mathematical physics, space physics"),
        ("chemistry", "Chemistry",
         "organic, inorganic, physical and analytical chemistry, chemical biology"),
        ("math_stats", "Mathematics & Statistics",
         "algebra, geometry, topology, differential equations, probability, numerical analysis, optimization, statistics theory"),
        ("computing", "Computer Science & IT",
         "artificial intelligence and machine learning, cybersecurity, data science, information theory, computational systems"),
        ("astronomy", "Astronomy & Planetary Science",
         "astrophysics, observational astronomy, planetary geology, cosmology"),
        ("materials", "Materials & Nanoscience",
         "nanomaterials, polymers, metallurgy, semiconductors, energy materials"),
    ]),
    ("engineering", "Engineering & Technology", [
        ("core_engineering", "Core Engineering",
         "mechanical, electrical, civil, chemical and aerospace engineering"),
        ("applied_tech", "Applied & Emerging Tech",
         "biomedical engineering, robotics, automation and control systems, energy science, biotechnology"),
    ]),
    ("life", "Biological & Life Sciences", [
        ("cell_molecular", "Cellular & Molecular",
         "cell biology, molecular biology, genetics, genomics, biochemistry, structural biology"),
        ("organismal", "Organismal & Systems",
         "microbiology, immunology, neuroscience, physiology, developmental biology, evolutionary biology"),
        ("ecology", "Ecology & Biodiversity",
         "ecology, conservation biology, zoology, plant sciences, entomology, computational biology and bioinformatics"),
    ]),
    ("health", "Health & Medical Sciences", [
        ("clinical", "Clinical & Disease Research",
         "oncology, cardiology, neurology, infectious diseases, clinical immunology"),
        ("therapeutics", "Therapeutics & Care",
         "pharmacology, drug discovery, nursing, dentistry, medical informatics, public and occupational health"),
        ("behavioral", "Behavioral & Mental Health",
         "clinical, cognitive, experimental and social psychology, behavioral sciences"),
    ]),
    ("earth", "Earth & Environmental Sciences", [
        ("earth_water", "Earth & Water",
         "geology (solid Earth), hydrology, ocean sciences, limnology, natural hazards"),
        ("climate", "Climate & Environment",
         "climate science, atmospheric science, environmental science, biogeochemistry, sustainability"),
    ]),
    ("society", "Society, Policy & Interdisciplinary Studies", [
        ("social_economic", "Social & Economic Sciences",
         "economics, finance, sociology, political science, public policy, education, geography"),
        ("resources", "Resource & Applied Fields",
         "agriculture, forestry, water resources, food science, veterinary science, science communication and ethics"),
    ]),
]

TOPICS = {tid: {"id": tid, "name": name, "covers": covers, "group": gid, "group_name": gname}
          for gid, gname, topics in GROUPS for tid, name, covers in topics}
TOPIC_IDS = list(TOPICS)


def topic_name(tid: str | None) -> str:
    return TOPICS[tid]["name"] if tid in TOPICS else ""


def prompt_list() -> str:
    """Topic list for the ranking prompt."""
    lines = []
    for gid, gname, topics in GROUPS:
        lines.append(f"{gname}:")
        lines += [f"  - {tid}: {name} ({covers})" for tid, name, covers in topics]
    return "\n".join(lines)


def as_json() -> list[dict]:
    return [{"id": gid, "name": gname, "topics": [{"id": t, "name": n, "covers": c} for t, n, c in topics]}
            for gid, gname, topics in GROUPS]
