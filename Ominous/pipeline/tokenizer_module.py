import tiktoken

class Tokenizer:
    def __init__(self, model_name="gpt-4"):
        # We use tiktoken for extremely fast BPE tokenization
        try:
            self.enc = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self.enc = tiktoken.get_encoding("cl100k_base")

    def encode(self, text):
        """
        Returns a list of integer token IDs.
        """
        return self.enc.encode(text, allowed_special="all")
