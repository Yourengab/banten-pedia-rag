from database.supabase import supabase

response = (
    supabase
    .table("banten_entities")
    .select("id")
    .limit(1)
    .execute()
)

print("Supabase connected successfully!")
print(response.data)    