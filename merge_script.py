import os
import json

folders = [
    "/Users/yourengab/Desktop/Projects/banten-pedia-model/data/Data Surya 2",
    "/Users/yourengab/Desktop/Projects/banten-pedia-model/data/Data Gungde",
    "/Users/yourengab/Desktop/Projects/banten-pedia-model/data/Data Devan (masih pisah)",
    "/Users/yourengab/Desktop/Projects/banten-pedia-model/data/Data Wirya (bahasa bali ke indonesia)"
]

output_file = "/Users/yourengab/Desktop/Projects/banten-pedia-model/web_viz/data.json"

merged_banten = []

# Load existing web_viz data just in case (optional, we'll include it)
if os.path.exists(output_file):
    try:
        with open(output_file, 'r') as f:
            data = json.load(f)
            if "banten" in data and isinstance(data["banten"], list):
                merged_banten.extend(data["banten"])
    except Exception as e:
        print(f"Error loading {output_file}: {e}")

for folder in folders:
    if not os.path.exists(folder):
        print(f"Folder not found: {folder}")
        continue
        
    for filename in os.listdir(folder):
        if not filename.endswith(".json"):
            continue
            
        filepath = os.path.join(folder, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
                # Handle different formats
                if isinstance(data, dict):
                    if "banten" in data:
                        banten_data = data["banten"]
                        if isinstance(banten_data, list):
                            merged_banten.extend(banten_data)
                        elif isinstance(banten_data, dict):
                            merged_banten.append(banten_data)
                    elif "nama" in data:
                        merged_banten.append(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            if "banten" in item:
                                merged_banten.append(item["banten"])
                            elif "nama" in item:
                                merged_banten.append(item)
        except Exception as e:
            print(f"Error processing {filepath}: {e}")

# Remove duplicates based on 'nama' (case-insensitive) if any
seen_names = set()
unique_banten = []
for b in merged_banten:
    if isinstance(b, dict) and "nama" in b and isinstance(b["nama"], str) and b["nama"].strip():
        name = b["nama"].strip().lower()
        if name not in seen_names:
            seen_names.add(name)
            unique_banten.append(b)

final_data = {"banten": unique_banten}

with open(output_file, 'w') as f:
    json.dump(final_data, f, indent=4)

print(f"Successfully merged {len(unique_banten)} unique banten items into {output_file}")
