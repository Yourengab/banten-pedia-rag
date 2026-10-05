from database.supabase import supabase

response = (
    supabase
    .table("banten")
    .select("id_banten")
    .limit(1)
    .execute()
)

print("Supabase connected successfully!")
print(response.data)    