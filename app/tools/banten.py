from database.supabase import supabase


def search_banten(
    query: str,
    wilayah: str | None = None,
    limit: int = 5
) -> list[dict]:
    """Search banten by name and optional region."""

    limit = max(1, min(limit, 20))

    banten_query = (
        supabase
        .table("banten")
        .select(
            "id_banten, nama_banten, nama_lokal, "
            "id_wilayah, deskripsi_umum"
        )
    )

    if query.strip():
        banten_query = banten_query.ilike(
            "nama_banten",
            f"%{query.strip()}%"
        )

    if wilayah and wilayah.strip():
        wilayah_response = (
            supabase
            .table("wilayah")
            .select("id_wilayah")
            .ilike("kabupaten", f"%{wilayah.strip()}%")
            .execute()
        )

        wilayah_ids = [
            item["id_wilayah"]
            for item in wilayah_response.data
        ]

        if not wilayah_ids:
            return []

        banten_query = banten_query.in_(
            "id_wilayah",
            wilayah_ids
        )

    response = banten_query.limit(limit).execute()

    results = []

    for item in response.data:
        wilayah_response = (
            supabase
            .table("wilayah")
            .select("kabupaten, kecamatan, desa_adat")
            .eq("id_wilayah", item["id_wilayah"])
            .limit(1)
            .execute()
        )

        item["wilayah"] = (
            wilayah_response.data[0]
            if wilayah_response.data
            else None
        )

        results.append(item)

    return results


def get_banten(banten_id: str) -> dict | None:
    """Get one banten with its region details."""

    response = (
        supabase
        .table("banten")
        .select("*")
        .eq("id_banten", banten_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    banten = response.data[0]

    if banten.get("id_wilayah"):
        wilayah_response = (
            supabase
            .table("wilayah")
            .select("*")
            .eq("id_wilayah", banten["id_wilayah"])
            .limit(1)
            .execute()
        )

        banten["wilayah"] = (
            wilayah_response.data[0]
            if wilayah_response.data
            else None
        )

    return banten


def get_components(banten_id: str) -> list[dict]:
    """Get components belonging to a banten."""

    relation_response = (
        supabase
        .table("banten_komponen")
        .select("id_komponen, jumlah")
        .eq("id_banten", banten_id)
        .execute()
    )

    relations = relation_response.data

    if not relations:
        return []

    component_ids = [
        item["id_komponen"]
        for item in relations
    ]

    component_response = (
        supabase
        .table("komponen")
        .select("*")
        .in_("id_komponen", component_ids)
        .execute()
    )

    components_by_id = {
        item["id_komponen"]: item
        for item in component_response.data
    }

    results = []

    for relation in relations:
        component = components_by_id.get(
            relation["id_komponen"]
        )

        if component:
            component["jumlah"] = relation["jumlah"]
            results.append(component)

    return results