import struct
import os
import numpy as np

class BinaryWriter:
    def __init__(self, output_prefix, dtype=np.uint32):
        self.bin_path = f"{output_prefix}.bin"
        self.idx_path = f"{output_prefix}.idx"
        self.dtype = dtype
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(os.path.abspath(self.bin_path)), exist_ok=True)
        
        self.bin_file = open(self.bin_path, 'wb')
        self.idx_file = open(self.idx_path, 'wb')
        
        # .idx format: for each document, we store (offset, length)
        # offset is uint64 (8 bytes), length is uint32 (4 bytes)
        self.current_offset = 0

    def write_document(self, token_ids):
        """Writes a single document's tokens and updates the index."""
        if not token_ids:
            return

        # Convert to numpy array
        arr = np.array(token_ids, dtype=self.dtype)
        
        # Length in terms of number of tokens
        length = len(arr)
        
        # Write to .bin
        byte_data = arr.tobytes()
        self.bin_file.write(byte_data)
        
        # Write to .idx (offset, length)
        self.idx_file.write(struct.pack('<QQ', self.current_offset, length))
        
        # Update offset (in bytes)
        self.current_offset += len(byte_data)

    def close(self):
        self.bin_file.close()
        self.idx_file.close()
