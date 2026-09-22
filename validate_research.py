import os
import sys

os.chdir(r"F:\Obscuro Ominous")
sys.path.insert(0, os.path.join(os.getcwd(), "Ominous"))

from pipeline.research_browser import research
from pipeline.dataset_store import verify_and_commit

text, urls = research("medical virology", min_chars=300)
print("URL_COUNT", len(urls))
print("URLS", urls[:3])
print("TEXT_LEN", len(text))
print("HAS_MULTISOURCE", len(urls) > 1)

blocks = [p.strip() for p in text.split("\n\n") if p.strip()]
docs = []
for i, block in enumerate(blocks[:6], 1):
    if len(block) >= 150:
        docs.append({
            "keyword": f"doc_{i}",
            "topic": "medical virology",
            "text": block[:2000],
        })
print("DOCS_READY", len(docs))
print("VERIFY", verify_and_commit(docs, "validation_virology_dataset", "medical virology", model_name=None))
