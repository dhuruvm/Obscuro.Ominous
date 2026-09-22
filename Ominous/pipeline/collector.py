import json
import os

class DataCollector:
    def __init__(self, input_path, chunk_size=1000):
        self.input_path = input_path
        self.chunk_size = chunk_size

    def iter_chunks(self):
        """Yields chunks of documents from the input file."""
        chunk = []
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input path {self.input_path} not found.")

        is_jsonl = self.input_path.endswith('.jsonl')

        with open(self.input_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                if is_jsonl:
                    try:
                        data = json.loads(line)
                        text = data.get('text', '')
                        if text:
                            chunk.append(text)
                    except json.JSONDecodeError:
                        continue
                else:
                    chunk.append(line)

                if len(chunk) >= self.chunk_size:
                    yield chunk
                    chunk = []
            
            if chunk:
                yield chunk
