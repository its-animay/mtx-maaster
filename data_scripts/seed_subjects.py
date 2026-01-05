"""
Seed ~45 real-world "subjects" directly into MongoDB (no API key required).

✅ What it does
- Builds a realistic subject catalog (Class 6–12 + competitive + CS skills)
- Generates clean slugs (e.g., "physics-class-9", "maths-class-11")
- Inserts subjects via the Database repository (avoids HTTP/auth)
- Skips subjects already present by slug

How to run:
1) Ensure MongoDB is reachable per your `.env` (MQDB_MONGO_URI/MQDB_MONGO_DB_NAME)
2) python seed_subjects.py
"""

import os
import sys
import re
from datetime import datetime
from typing import Dict, List, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import Database  # type: ignore
from app.schemas.master import SubjectResponse  # type: ignore


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def make_subject(
    name: str,
    description: str,
    tags: List[str],
    metadata: Dict[str, Any],
    is_active: bool = True,
    slug: str = None,
) -> Dict[str, Any]:
    return {
        "name": name,
        "slug": slug or slugify(name),
        "description": description,
        "tags": tags,
        "metadata": metadata,
        "is_active": is_active,
    }


def build_subjects() -> List[Dict[str, Any]]:
    owner = "curriculum-team"
    boards = ["CBSE", "ICSE", "State Boards"]
    langs = ["en", "hi"]
    version = "1.0"

    subjects: List[Dict[str, Any]] = []

    # -------- Class 6–10 (Core) --------
    core_6_10 = [
        ("Mathematics", "math"),
        ("Science", "science"),
        ("English", "english"),
        ("Hindi", "hindi"),
        ("Social Science", "sst"),
        ("Computer Applications", "computers"),
    ]

    for cls in [6, 7, 8, 9, 10]:
        for base, tag in core_6_10:
            name = f"{base} (Class {cls})"
            desc = f"{base} curriculum for Class {cls} focusing on core concepts, examples, and practice aligned to school boards."
            tags = ["school", f"class-{cls}", tag] + (["boards"] if base != "Computer Applications" else ["coding"])
            meta = {
                "owner": owner,
                "level": f"class-{cls}",
                "boards": boards,
                "exam_alignment": ["School Exams"],
                "language_support": langs,
                "version": version,
                "grade_range": [cls, cls],
                "stream": "school",
            }
            subjects.append(make_subject(name, desc, tags, meta, slug=slugify(f"{base} class {cls}")))

    # -------- Class 11–12 (Streams) --------
    stream_11_12 = [
        ("Physics", ["science", "physics"]),
        ("Chemistry", ["science", "chemistry"]),
        ("Mathematics", ["math", "mathematics"]),
        ("Biology", ["science", "biology"]),
        ("English", ["english", "language"]),
        ("Computer Science", ["computers", "coding"]),
        ("Informatics Practices", ["computers", "data"]),
        ("Accountancy", ["commerce", "accounting"]),
        ("Business Studies", ["commerce", "business"]),
        ("Economics", ["commerce", "economics"]),
        ("Political Science", ["humanities", "politics"]),
        ("History", ["humanities", "history"]),
        ("Geography", ["humanities", "geography"]),
        ("Psychology", ["humanities", "psychology"]),
    ]

    for cls in [11, 12]:
        for base, base_tags in stream_11_12:
            name = f"{base} (Class {cls})"
            desc = f"{base} for Class {cls} with concept-first learning, structured notes, and board-exam style practice."
            tags = ["school", f"class-{cls}"] + base_tags + ["boards"]
            meta = {
                "owner": owner,
                "level": f"class-{cls}",
                "boards": boards,
                "exam_alignment": ["Board Exams"],
                "language_support": langs,
                "version": version,
                "grade_range": [cls, cls],
                "stream": "school",
            }
            subjects.append(make_subject(name, desc, tags, meta, slug=slugify(f"{base} class {cls}")))

    # -------- Competitive / Entrance (JEE/NEET) --------
    competitive = [
        ("JEE Physics", "JEE Physics covering mechanics, electricity & magnetism, optics, thermodynamics and modern physics with advanced problem-solving.",
         ["science", "physics", "jee"], ["JEE Main", "JEE Advanced"]),
        ("JEE Chemistry", "JEE Chemistry spanning physical, organic and inorganic chemistry with mechanisms, numericals and advanced practice.",
         ["science", "chemistry", "jee"], ["JEE Main", "JEE Advanced"]),
        ("JEE Mathematics", "JEE Mathematics with algebra, calculus, coordinate geometry, vectors and probability with high-quality problems.",
         ["math", "mathematics", "jee"], ["JEE Main", "JEE Advanced"]),
        ("NEET Physics", "NEET Physics with concept clarity, formula application and exam-style problem practice.",
         ["science", "physics", "neet"], ["NEET"]),
        ("NEET Chemistry", "NEET Chemistry across physical, organic, inorganic with NCERT-first approach and MCQ practice.",
         ["science", "chemistry", "neet"], ["NEET"]),
        ("NEET Biology", "NEET Biology covering botany and zoology with diagrams, NCERT alignment and MCQs.",
         ["science", "biology", "neet"], ["NEET"]),
    ]

    for title, desc, tags, alignment in competitive:
        meta = {
            "owner": owner,
            "level": "competitive",
            "boards": boards,
            "exam_alignment": alignment,
            "language_support": langs,
            "version": version,
            "grade_range": [11, 12],
            "stream": "competitive",
        }
        subjects.append(make_subject(title, desc, tags + ["foundation"], meta))

    # -------- Skills / CS / Data (real-world) --------
    skills = [
        ("Python Programming", "Python from basics to intermediate with problem-solving, OOP, and practical projects.",
         ["programming", "python", "coding"]),
        ("Data Structures & Algorithms", "DSA covering arrays, stacks, queues, trees, graphs, DP with interview-style practice.",
         ["programming", "dsa", "interview"]),
        ("Web Development", "HTML, CSS, JavaScript fundamentals plus project-based learning for modern web apps.",
         ["programming", "web", "javascript"]),
        ("Database & SQL", "SQL fundamentals to advanced queries, joins, indexing, and schema design with exercises.",
         ["database", "sql", "data"]),
        ("Statistics for Data Science", "Core statistics including probability, distributions, estimation, hypothesis testing with examples.",
         ["data-science", "statistics", "math"]),
        ("Machine Learning Foundations", "Supervised/unsupervised learning basics, evaluation, feature engineering and model training workflows.",
         ["data-science", "machine-learning", "ai"]),
    ]

    for title, desc, tags in skills:
        meta = {
            "owner": owner,
            "level": "skill",
            "boards": [],
            "exam_alignment": ["Skill Track"],
            "language_support": ["en"],
            "version": version,
            "grade_range": None,
            "stream": "skills",
        }
        subjects.append(make_subject(title, desc, tags + ["foundation"], meta))

    # Ensure we have 40+ (we actually have more)
    return subjects


def main():
    subjects = build_subjects()
    db = Database()
    print(f"Seeding {len(subjects)} subjects directly into MongoDB database '{db.db_name}'\n")

    inserted = 0
    skipped = 0
    now = datetime.utcnow()

    for i, subj in enumerate(subjects, start=1):
        slug = subj["slug"]
        if db.get_subject_by_slug(slug):
            skipped += 1
            print(f"[{i:02d}/{len(subjects)}] ↷ SKIP  slug={slug}  (already exists)")
            continue

        subject_doc = SubjectResponse(
            id=f"subject_{slug}",
            name=subj["name"],
            slug=slug,
            description=subj.get("description"),
            tags=subj.get("tags", []),
            metadata=subj.get("metadata"),
            is_active=subj.get("is_active", True),
            created_at=now,
            updated_at=now,
        )
        db.insert_subject(subject_doc)
        inserted += 1
        print(f"[{i:02d}/{len(subjects)}] ✅ OK   slug={slug}")

    print("\nDone.")
    print(f"Inserted: {inserted}")
    print(f"Skipped (existing): {skipped}")


if __name__ == "__main__":
    main()
