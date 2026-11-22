from typing import Any, cast
import logging

from database.supabase import supabase

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
SEARCH_THRESHOLD_HIGH = 0.6
SEARCH_THRESHOLD_GAP = 0.2
SEARCH_THRESHOLD_LOW = 0.3


def search_entities(
    query_data: dict,
    limit: int = 5
) -> dict:
    """
    Search across banten_entities using fuzzy matching (ILIKE / similarity)
    and structured scoring.
    """
    core = query_data.get("core", "")
    variants = query_data.get("variants", [])
    all_terms = list(set([core] + variants))
    
    limit = max(1, min(limit, 20))
    all_results = []
    
    for term in all_terms:
        if not term or len(term) < 2:
            continue
            
        try:
            # Query langsung ke banten_entities karena komponen & bahan ada di sini
            response = (
                supabase
                .table("banten_entities")
                .select("id, name, description, type")
                .ilike("name", f"%{term}%")
                .limit(limit)
                .execute()
            )
            
            for item in (response.data or []):
                all_results.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "entity_type": item.get("type", "banten"),
                    "similarity": 0.7  # Nominal score untuk ILIKE match
                })
        except Exception as exc:
            logger.warning(f"[Tools] Search failed for term {term}: {exc}")

    # Deduplicate by id and keep highest similarity
    unique_results = {}
    for r in all_results:
        key = str(r['id'])
        if key not in unique_results or r['similarity'] > unique_results[key]['similarity']:
            unique_results[key] = r
            
    sorted_results = sorted(unique_results.values(), key=lambda x: x['similarity'], reverse=True)
    top_matches = sorted_results[:limit]
    
    # Apply Scoring Logic (Disambiguation)
    ambiguous = False
    final_data = []
    
    if len(top_matches) > 0:
        top_score = top_matches[0]["similarity"]
        
        if top_score >= SEARCH_THRESHOLD_HIGH:
            if len(top_matches) > 1:
                gap = top_score - top_matches[1]["similarity"]
                if gap < SEARCH_THRESHOLD_GAP:
                    ambiguous = True
            else:
                ambiguous = False
            
            if not ambiguous:
                final_data = [top_matches[0]]
            else:
                final_data = top_matches[:5]
        elif top_score >= SEARCH_THRESHOLD_LOW:
            ambiguous = True
            final_data = top_matches[:5]
        else:
            final_data = []

    options = [
        {"id": item["id"], "type": item["entity_type"], "label": f"{item['name']} ({item['entity_type']})"}
        for item in final_data
    ]

    return {
        "ambiguous": ambiguous,
        "options": options,
        "data": final_data,
        "top_score": top_matches[0]["similarity"] if top_matches else 0.0
    }


def search_banten(
    query: str,
    wilayah: str | None = None,
    limit: int = 5
) -> dict:
    return search_entities({"core": query, "variants": []}, limit)


def get_banten(banten_id: str) -> dict | None:
    """Get one entity from banten_entities."""
    response = (
        supabase
        .table("banten_entities")
        .select("*")
        .eq("id", banten_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return cast(dict[str, Any], response.data[0])


def get_components(banten_id: str) -> list[dict]:
    """Get child entities connected via banten_relations."""
    relation_response = (
        supabase
        .table("banten_relations")
        .select("child_id, notes")
        .eq("parent_id", banten_id)
        .execute()
    )

    relations = relation_response.data
    if not relations:
        return []

    child_ids = [item["child_id"] for item in relations]

    child_response = (
        supabase
        .table("banten_entities")
        .select("*")
        .in_("id", child_ids)
        .execute()
    )

    children_by_id = {item["id"]: item for item in (child_response.data or [])}

    results = []
    for rel in relations:
        child = children_by_id.get(rel["child_id"])
        if child:
            child["notes"] = rel.get("notes")
            results.append(child)

    return results


def get_full_relation_tree(banten_id: str, max_depth: int = 3) -> list[dict]:
    """
    Recursively fetch all components and their materials.
    Returns a flat list of all related entities with hierarchy info.
    
    Args:
        banten_id: Root entity ID
        max_depth: Maximum recursion depth (default 3: banten -> komponen -> bahan)
    
    Returns:
        List of dicts with keys: id, name, type, description, level, parent_name, notes
    """
    all_relations = []
    visited = set()
    
    def _fetch_children(parent_id: str, level: int, parent_name: str = ""):
        if level >= max_depth or parent_id in visited:
            return
        visited.add(parent_id)
        
        children = get_components(parent_id)
        for child in children:
            child_id = child.get("id")
            child_type = child.get("type", "komponen")
            
            # Add to flat list with hierarchy info
            all_relations.append({
                "id": child_id,
                "name": child.get("name"),
                "type": child_type,
                "description": child.get("description"),
                "level": level,
                "parent_name": parent_name,
                "notes": child.get("notes", "")
            })
            
            # If it's a komponen, fetch its materials (bahan)
            if child_type == "komponen" and level < max_depth:
                _fetch_children(child_id, level + 1, child.get("name", ""))
    
    _fetch_children(banten_id, 1)
    return all_relations


def get_komponen_detail(komponen_id: str) -> dict | None:
    return get_banten(komponen_id)


def get_bahan_detail(bahan_id: str) -> dict | None:
    return get_banten(bahan_id)