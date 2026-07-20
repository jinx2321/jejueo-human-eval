import json
import os
import random

def main():
    # 1. Set a fixed random seed
    random.seed(42)
    
    # 2. Load the central database of sentences
    database_path = os.path.join("data", "central_database.json")
    try:
        with open(database_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Database file `{database_path}` not found.")
        return
    except Exception as e:
        print(f"Error loading database: {str(e)}")
        return

    # 3. Sample 100 entries using the fixed seed
    total_sentences = len(data)
    sample_size = min(100, total_sentences)
    sampled_indices = random.sample(range(total_sentences), sample_size)
    
    # Sort the sampled indices to keep navigation sequential
    sampled_indices.sort()
    
    # 4. Generate the sampled dataset while preserving the original index
    sampled_data = []
    for idx in sampled_indices:
        item = data[idx].copy()
        item["original_index"] = idx
        sampled_data.append(item)
        
    # 5. Save the batch to a static file
    output_path = os.path.join("data", "evaluation_batch_100.json")
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sampled_data, f, indent=2, ensure_ascii=False)
        print(f"Successfully sampled {len(sampled_data)} sentences.")
        print(f"Saved static batch to `{output_path}`.")
    except Exception as e:
        print(f"Error saving sampled batch: {str(e)}")

if __name__ == "__main__":
    main()
