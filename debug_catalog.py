# debug_catalog.py
import json

# Open with UTF-8 encoding
with open('data/catalog.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'Total items: {len(data)}')
print('\nFirst 20 items in catalog:')
for i, item in enumerate(data[:20], 1):
    print(f'{i}. {item["name"]} - Type: {item.get("test_type", "O")}')

# Check for Java-related items
print('\n=== Java-related assessments ===')
java_items = [item for item in data if 'java' in item['name'].lower()]
print(f'Found {len(java_items)} Java-related assessments:')
for item in java_items[:10]:
    print(f'  - {item["name"]} (Type: {item.get("test_type", "O")})')

# Check for technical assessments
tech_keywords = ['java', 'python', 'javascript', 'sql', 'aws', 'docker', 'spring', 'react']
tech_items = []
for item in data:
    name = item['name'].lower()
    for keyword in tech_keywords:
        if keyword in name:
            tech_items.append(item['name'])
            break

print(f'\nFound {len(tech_items)} technical assessments:')
for name in tech_items[:15]:
    print(f'  - {name}')