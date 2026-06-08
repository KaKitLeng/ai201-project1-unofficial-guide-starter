import ingest
from embed import retrieve

# cs = ingest.build_chunks()

# # 1. Per-listing counts — find out why listings = 355 chunks
# import collections
# print(collections.Counter(c['metadata']['source_file'] for c in cs))

# # 2. The OCCL chunk with your Q5 ground truth — must be intact, not split
# for c in cs:
#     if c['metadata']['source_type'] == 'legal' and '45' in c['text'] and 'day' in c['text'].lower():
#         print('--- OCCL 45-day chunk ---')
#         print(c['text'])

# # 3. A few Legacy 202 chunks — check for junk + that rent/pets survived
# for c in cs:
#     if c['metadata']['source_file'].startswith('legacy202'):
#         print('--- legacy202 chunk', c['metadata']['chunk_index'], '---')
#         print(c['text'][:400])

# 4
for r in retrieve("Which apartments within ~1 mile of the Main Quad have in-unit laundry and a unit renting under ~$1,000/month (by-the-bed pricing counts)??",k=8):
    print("are pets allowed at Legacy 202?")   # your Q2
    print(round(r["distance"], 3), r["metadata"]["source_file"], "::", r["text"][:120])

for r in retrieve("management complaints", k=3, where={"building": "Pacifica on Green"}):
    print("management complaints")   # your Q4
    print(round(r["distance"], 3), r["metadata"]["source_file"])