import struct
import numpy as np
import tiktoken
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Read Indexed Binary (.bin/.idx) file")
    parser.add_argument("--prefix", "-p", type=str, required=True, help="Prefix of .bin and .idx files")
    parser.add_argument("--doc-id", "-d", type=int, required=True, help="Document ID to read (0-indexed)")
    return parser.parse_args()

def read_document(prefix, doc_id):
    bin_path = f"{prefix}.bin"
    idx_path = f"{prefix}.idx"
    
    with open(idx_path, 'rb') as f_idx:
        # Seek to the index for the document: each entry is 12 bytes (8 for uint64 offset, 4 for uint32 length)
        f_idx.seek(doc_id * 12)
        idx_data = f_idx.read(12)
        if not idx_data:
            print(f"Document ID {doc_id} out of bounds.")
            return
            
        offset, length = struct.unpack('<QI', idx_data)
        
    print(f"Document {doc_id} -> Offset: {offset} bytes, Length: {length} tokens")
    
    with open(bin_path, 'rb') as f_bin:
        f_bin.seek(offset)
        # We used uint32 (4 bytes per token)
        bin_data = f_bin.read(length * 4)
        
    token_ids = np.frombuffer(bin_data, dtype=np.uint32)
    
    enc = tiktoken.get_encoding("cl100k_base")
    text = enc.decode(token_ids.tolist())
    
    print("--------------------------------------------------")
    print(text)
    print("--------------------------------------------------")

if __name__ == "__main__":
    args = parse_args()
    read_document(args.prefix, args.doc_id)
