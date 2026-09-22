import multiprocessing as mp
from pipeline.cleaner import DataCleaner
from pipeline.tokenizer_module import Tokenizer

# Global instances per worker process
_cleaner = None
_tokenizer = None

def init_worker():
    global _cleaner, _tokenizer
    _cleaner = DataCleaner()
    _tokenizer = Tokenizer()

def process_chunk(texts):
    """
    Worker function to process a list of raw texts.
    Cleans and tokenizes them.
    """
    results = []
    junk_count = 0
    for text in texts:
        cleaned = _cleaner.clean(text)
        if cleaned:
            token_ids = _tokenizer.encode(cleaned)
            if token_ids:
                results.append(token_ids)
            else:
                junk_count += 1
        else:
            junk_count += 1
            
    return results, junk_count

class JobManager:
    def __init__(self, num_workers):
        self.num_workers = num_workers
        self.pool = mp.Pool(processes=self.num_workers, initializer=init_worker)

    def process_data(self, chunk_iterator):
        """
        Yields (processed_documents_list, junk_count) for each chunk.
        """
        # imap yields results as soon as they are ready, in order.
        # imap_unordered is faster if order doesn't matter, but for reproducibility we can use imap.
        for results, junk_count in self.pool.imap(process_chunk, chunk_iterator):
            yield results, junk_count

    def close(self):
        self.pool.close()
        self.pool.join()
