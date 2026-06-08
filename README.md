# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

I chose off-campus housing at the University of Illinois Urbana-Champaign (UIUC). Official channels like the listing sites, the leasing offices, the university's housing pages, will tell you a unit's rent, square footage, and amenities, but they won't tell you the things that actually decide whether you have a good year such as which landlords actually fix things, which buildings have noise, pests, or deposit-withholding problems, and whether a pricier Campustown high-rise is worth it over a cheaper apartment in an Urbana neighborhood. That lived-experience knowledge is real but scattered across Reddit threads, Google reviews, and word of mouth, and there's no single place to search it, which is exactly the gap this system fills. 

---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | Legacy 202 (Champaign) | Rent, beds/baths, pet policy, amenities - *paired with Reddit #12* | https://www.apartments.com/legacy202-champaign-il/bct4hpc/ |
| 2 | The Linc (Urbana) | Rent, amenities, lease terms - *paired with Reddit #13* | https://www.apartments.com/the-linc-apartments-urbana-il/3lf7bxf/ |
| 3 | Maywood (Champaign) | Rent, amenities - *paired with Reddit #14* | https://www.apartments.com/maywood-apartments-champaign-il/jcvk767/ |
| 4 | The Alcove at Second & John (Champaign) | Rent, amenities - *paired with Reddit #15* | https://www.apartments.com/the-alcove-second-john-champaign-il/fv2vltr/ |
| 5 | 202 E Green by Bankier (Champaign) | Rent, amenities - **listings-only** (no Reddit thread) | https://www.apartments.com/202-e-green-st-by-bankier-apartments-champaign-il/vn1k7tf/ |
| 6 | Pacifica on Green (Champaign) | Rent, amenities - *paired with Reddit #16* | https://www.apartments.com/pacifica-on-green-champaign-il/qdf14jw/ |
| 7 | Campus Oaks (Urbana) | Rent, amenities - *paired with Reddit #17* | https://www.apartments.com/campus-oaks-urbana-il/l1ydpfg/ |
| 8 | Alley Lofts at the Pilot (Champaign) | Rent, amenities - **listings-only** (no Reddit thread) | https://www.apartments.com/alley-lofts-at-the-pilot-champaign-il/m83pnvh/ |
| 9 | OCCL (Off-Campus Community Living) | Official UIUC off-campus office for security deposits, subleasing, tenant rights, scam avoidance. The only source for the Q5 process, without it Q5 has nothing to ground in. | https://occl.illinois.edu/rights-and-responsibilities/rights/summary |
| 10 | r/UIUC - "Please do not live at Legacy 202" | Strong negative resident experience — pairs with listing #1 | https://www.reddit.com/r/UIUC/comments/16xycks/please_do_not_live_at_legacy_202/ |
| 11 | r/UIUC - "Experience with The Linc Apartments" | Resident experience - pairs with listing #2 | https://www.reddit.com/r/UIUC/comments/140prcv/experience_with_the_linc_apartments/ |
| 12 | r/UIUC - "Maywood Apartments…never live here" | Strong negative - pairs with listing #3 | https://www.reddit.com/r/UIUC/comments/ipx5hh/maywood_apartmentsnever_live_here/ |
| 13 | r/UIUC - "Reviews on The Alcove at Second and John" | Resident experience - pairs with listing #4 | https://www.reddit.com/r/UIUC/comments/1bh3d58/reviews_on_the_alcove_at_second_and_john/ |
| 14 | r/UIUC - "Sophomore apartment recommendations" | General recommendations across buildings (breadth, not tied to one building) | https://www.reddit.com/r/UIUC/comments/166pc1v/sophomore_apartment_recommendations/ |
| 15 | r/UIUC - "Don't sign with Pacifica on Green" | Strong negative - pairs with listing #6 | https://www.reddit.com/r/UIUC/comments/1o6pln5/dont_sign_with_pacifica_on_greenpog/ |
| 16 | r/UIUC - "Campus Oaks Apartments" | Resident experience - pairs with listing #7 | https://www.reddit.com/r/UIUC/comments/hnsu5a/campus_oaks_apartments/ |

---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:** target ~500 characters (~ 100-125 tokens), hard cap below the embedding model's 256-token limit.

**Overlap:** ~75 characters, applied only when a long document is actually split. Short records that fit under the cap pass through whole with no overlap added.

**Why these choices fit your documents:** The corpus is *heterogeneous*, so chunking is recursive and content-aware rather than blind fixed-size. Of the three standard strategies, fixed-size, semantic, and recursive, I rejected fixed-size (it would slice short self-contained reviews into meaningless fragments), deferred semantic (it requires running the embedder during chunking for little payoff on already-short records), and used recursive splitting on a separator priority of paragraph -> line -> sentence -> word -> character, falling to a finer separator only when a piece exceeds the size cap. This keeps short reviews and listing facts intact as one chunk each (one record = one chunk, fully attributable), while long documents like the OCCL ordinance split on natural Q&A boundaries with overlap so a fact near a boundary (e.g. the 45-day deposit rule) stays retrievable.

**Final chunk count:** 263 chunks

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:** `all-MiniLM-L6-v2` via `sentence-transformers` which runs locally, no API key, no rate limits, 384-dimensional embeddings, and fast on CPU. Vectors are normalized and stored in a persistent ChromaDB collection configured with cosine distance. It's a good fit for the short review/listing text in this corpus.

**Production tradeoff reflection:** 
If I were deploying for real users and cost weren't a constraint, I'd weigh:
- **Accuracy on domain text:** a larger model (e.g. `bge-large`, OpenAI `text-embedding-3-large`, or Cohere embeds) would likely capture nuanced, slangy review language and building nicknames better than MiniLM, which can treat informal terms as near-noise.
- **Multilingual support:** UIUC has a very large international student population, and some reviews/threads appear in other languages. A multilingual model (e.g. `paraphrase-multilingual-MiniLM` or Cohere multilingual) would retrieve those instead of dropping them.
- **Local vs. API:** local gives privacy and zero marginal cost but caps quality; an API gives better recall at the cost of latency, spend, and a network dependency. For a student tool, local MiniLM is the right default but for a real product serving many users, I'd A/B a hosted model and measure retrieval accuracy against a labeled query set before paying for it.

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:** The LLM is given a system prompt that forbids outside knowledge rather than merely suggesting the documents:

> Answer the question using ONLY the information in the provided context. Do not use any outside or prior knowledge. If the context does not contain enough information to answer, respond with exactly: "I don't have enough information on that." Do not guess or fill gaps from general knowledge.

A backstop short-circuit returns the refusal without calling the LLM when retrieval returns nothing or the best chunk's distance exceeds a weak-match threshold (~0.8 cosine).

**How source attribution is surfaced in the response:** Attribution is programmatic, not LLM-generated which is a key design choice. After generation, the source list is built from the `source_file` metadata of the retrieved chunks (order-preserving dedupe), so the model's text can never fabricate, omit, or alter a citation. The response returns `{answer, sources, chunks}`, and the Gradio UI shows the answer and a "Retrieved from" list of source files. On a refusal, the source list is suppressed to empty.

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | What is the monthly rent for a 2 bedroom unit at Legacy 202 (202 E Daniel St)? | $1,275 for the 2x2C floor plan ($1,295 for 2x2A and 2x2B), from legacy202.txt. | The monthly rent for a 2 bedroom unit at Legacy 202 is $1,275 per person, from legacy202.txt | Relevant | Accurate |
| 2 | Are pets allowed at Legacy 202 (202 E Daniel St)? | No. legacy202.txt states Legacy202 does not allow pets. | No, pets are not allowed at Legacy202, though service animals are always welcome in accordance with applicable laws, from legacy202.txt | Relevant | Accurate |
| 3 | Which apartments within ~1 mile of the Main Quad have in-unit laundry and a unit renting under ~$1,000/month? | Maywood ~$899–995; Pacifica 4x3 ~$910–970. Note: this is a multi-unit answer spread across listings, if top-k is too low the system may return only one. | I don't have enough information on that. | Partially relevant | Inaccurate |
| 4 | What do people say about management/maintenance at Pacifica on Green (POG)? | Reviews are strongly negative on management. Per reddit_uiuc_1o6pln5.txt (r/UIUC, 2025): the office is described as unresponsive/dismissive — the advertised "luxury coffee bar" is frequently out of supplies, quiet-hours and overnight-guest violations the office declines to address, residents assigned the wrong unit at move-in, a refused internal transfer despite the lease allowing it, stolen food deliveries, and reports of delayed deposit returns. | There are management/maintenance issues, including a "luxury coffee bar" that is often unusable due to a lack of refills for the coffee machine, from reddit_uiuc_1o6pln5.txt | Relevant | Partially Accurate |
| 5 | Under the Urbana Landlord-Tenant Ordinance, how long does a landlord have to return a security deposit, and what can a tenant do if the landlord doesn't keep the unit in repair? | 45 days. | Landlord has 45 days after tenant moves out to return the deposit. If landlord doesn't keep the unit repair, the tenant may have the work done by a tradeperson | Relevant | Accurate|

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:** Q3 - "Which apartments within ~1 mile of the Main Quad have in-unit laundry and a unit renting under ~$1,000/month?"

**What the system returned:** "I don't have enough information on that."

**Root cause (tied to a specific pipeline stage):** This is a retrieval-completeness failure at the retrieval stage, confirmed by inspecting the top-8 retrieved chunks. The chunks were topically relevant (by-the-bed leasing, affordable, close to campus) but no single chunk contained a unit satisfying 3 conditions. The only price chunk retrieved showed Legacy's $1,275 2-bed (which doesn't qualify), while a qualifying unit's price, distance, and its in-unit-laundry status live in separate chunks in separate documents. Q3 is a multi-condition aggregation query that requires intersecting price + laundry + distance facts across the whole corpus, but semantic top-k retrieval surfaces chunks similar to the query phrase, not the complete set satisfying a conjunction. Given the fragmentation that don't contain a qualifying unit, the grounding prompt correctly refused rather than fabricate, so the refusal is honest.

**What you would change to fix it:** Store structured metadata per listing — a numeric `min_price` field and a boolean `in_unit_laundry` flag — and pre-filter with a metadata query *before* semantic ranking, so the system can compute the qualifying set deterministically rather than hoping similarity surfaces every piece. This is essentially the "Metadata Filtering" stretch feature, and it's the right tool for conjunctive/aggregation queries that vector search alone cannot serve.

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:** Writing the 5 evaluation questions in `planning.md` *before* building anything shaped every downstream decision and caught failures early. Because the questions named specific, verifiable facts (Legacy's $1,275 rent, the pet policy, the 45-day deposit rule), I could test retrieval against them at Milestone 4 and surface real bugs like Q2 pet answer being split across a chunk boundary, and the Q4 building name carrying no vector entry.

**One way your implementation diverged from the spec, and why:** The spec said `building` metadata would be attached to listings only. During implementation I extended it to Reddit chunks via the "thread-building" pairing, because Q4 ("management at Pacifica on Green") needs to connect reviews to a building, and the review body never says "Pacifica on Green" (it says "the office," "POG"). I also added a chunking rule not in the original spec, splitting the listing FAQ per question,  after the pet answer failed to retrieve because it was buried in a multi-topic FAQ blob, and I updated `planning.md` to reflect them.

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1** - Embedding/retrieval Q4 failure.

- *What I gave the AI:* My `planning.md` Retrieval Approach section and a request to implement `embed.py` (embedding with all-MiniLM-L6-v2, ChromaDB storage with my metadata schema, and a `retrieve()` function), plus my Q4 eval query as a test.

- *What it produced:* A working embedding/retrieval pipeline, but Q4 failed. The Pacifica review thread wasn't in the top results even with a building filter.

- *What I changed or overrode:* I directed the fix once I understood the cause (the building name lived in metadata/title, not the embedded body, so it carried no vector signal). I then embed a metadata-enriched string (`building | title \n body`) while still displaying the clean body. Q4 went from absent to rank 1.

**Instance 2** - Ingestion/chunking, Q2 failure.

- *What I gave the AI:* My Documents and Chunking Strategy sections and a request to implement the recursive splitter and type-specific cleaning, then later the Q2 retrieval failure (the pet answer wasn't surfacing).

- *What it produced:* The initial chunker kept each listing's FAQ as one multi-topic chunk, and the pet Q&A was split across a chunk boundary ("does not allow p" / "ets, service animals welcome").

- *What I changed or overrode:* I directed it to split the FAQ block per question so each answer is atomic. After rebuilding the index, the pet chunk retrieved at distance 0.163 (rank 1).
