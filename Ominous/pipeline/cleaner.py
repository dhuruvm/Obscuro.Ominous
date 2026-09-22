import re

class DataCleaner:
    def __init__(self, min_length=10, max_length=100000):
        self.min_length = min_length
        self.max_length = max_length
        # Simple regex to filter out HTML tags (industrial pipelines would use more robust parsers if needed)
        self.html_re = re.compile(r'<[^>]+>')

    def clean(self, text):
        """
        Returns cleaned text, or None if the document is considered junk.
        """
        if not text:
            return None
        
        # Remove HTML
        text = self.html_re.sub(' ', text)
        text = ' '.join(text.split()) # Normalize whitespace

        if len(text) < self.min_length or len(text) > self.max_length:
            return None
            
        # Add more advanced heuristic checks here (e.g., language id, toxicity)
        return text
