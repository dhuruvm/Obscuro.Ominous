import json
import random

def generate_dummy_data(filename, num_records):
    words = ["industrial", "data", "collector", "LLM", "training", "pipeline", "high", "performance", "binary", "indexed", "junk", "filtered"]
    
    with open(filename, 'w', encoding='utf-8') as f:
        for i in range(num_records):
            # Generate a document of random length
            doc_len = random.randint(5, 50)
            text = " ".join(random.choices(words, k=doc_len))
            
            # Occasionally generate junk (too short)
            if random.random() < 0.1:
                text = "short"
                
            record = {"id": i, "text": text}
            f.write(json.dumps(record) + "\n")

if __name__ == "__main__":
    generate_dummy_data("dummy_data.jsonl", 15000)
    print("Generated 15,000 records in dummy_data.jsonl")
