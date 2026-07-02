# search_test.py
import json
from app.catalog.loader import CatalogLoader
from app.catalog.indexer import CatalogIndexer
from app.catalog.retriever import CatalogRetriever

# Load catalog
loader = CatalogLoader()
catalog = loader.load()
print(f'Loaded {len(catalog)} items from catalog')

# Load index
indexer = CatalogIndexer()
if not indexer.load_index():
    print('Building index...')
    indexer.build_index(catalog)
    indexer.save_index()
else:
    print(f'Index loaded with {indexer.size} items')

retriever = CatalogRetriever(indexer)

# Search for different queries
queries = ['java', 'java developer', 'programming', 'personality', 'aws']

for query in queries:
    print(f'\n=== Searching for: "{query}" ===')
    results = retriever.search(query, top_k=5)
    
    if results:
        print(f'Found {len(results)} results:')
        for i, result in enumerate(results, 1):
            item = result['item']
            print(f'{i}. {item["name"]} (score: {result["score"]:.3f})')
    else:
        print('No results found!')

# Also try a direct search on the catalog
print('\n=== Direct catalog search for "java" ===')
with open('data/catalog.json', 'r', encoding='utf-8') as f:
    catalog = json.load(f)

java_items = [item for item in catalog if 'java' in item['name'].lower()]
print(f'Found {len(java_items)} items with "java" in name:')
for item in java_items[:10]:
    print(f'  - {item["name"]}')