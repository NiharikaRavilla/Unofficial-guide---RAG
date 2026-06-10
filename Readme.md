# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->
ASU Off-campus housing experiences is my domain. As an international student, when I first planned my trip, my main focus was on where to stay, but me and my friends did not have a clear channel to learn what the housing options were actually like. We searched everything on Google and eventually finalized a place, but having a searchable system with student experiences would help new students choose housing based on their own preferences, budget, commute, and comfort level. This knowledge is hard to find through official channels because apartment websites mostly show marketing information, while the most useful details for students often come from reviews, Reddit discussions, sublease posts, and unofficial guides. Those sources capture issues like noise, maintenance, pests, parking, walkability, and how far a place really feels from campus.
---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 |ASU Official Website |Official Listings |https://offcampushousing.asu.edu |
| 2 |College Pads |Housing Listings |https://www.rentcollegepads.com/off-campus-housing/asu/search |
| 3 |uhomes.com |Housing Listings |https://en.uhomes.com/us/tempe |
| 4 |Birdeye Reviews |Apartment Reviews |https://reviews.birdeye.com/the-district-on-apache-161368555711655 |
| 5 |RateMyApartments |Apartment Reviews |https://www.ratemyapartments.com/ratings/az/arizona-state-university-at-the-tempe-campus |
| 6 |Apartmentlist.com |Housing Listings |https://www.apartmentlist.com/off-campus-housing/az/asu-apartments-for-rent |
| 7 | Off-Campus Universe guide | Housing Guide | https://www.offcampus-universe.com/post/apartments-near-arizona-state-university-best-off-campus-housing-for-asu-students |
| 8 | Off-Campus Universe guide | Housing Guide | https://www.offcampus-universe.com/post/asu-off-campus-housing-guide-apartments-houses-and-subleases-in-tempe |
| 9 |Apartments to avoid |Reddit Discussion|https://www.reddit.com/r/ASU/search/?q=apartments |
| 10 |Do Any student Apartments NOT suck? |Reddit Discussion|https://www.reddit.com/r/ASU/search/?q=apartments |
| 11 |Housing takeover Megathread |https://www.reddit.com/r/ASU/search/?q=apartments |
| 12 |What Apartments are good in tempe near ASU? |https://www.reddit.com/r/ASU/search/?q=apartments |

---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:** 350-450 tokens

**Overlap:**60 tokens

**Why these choices fit your documents:**
My dataset contains a mixture of housing listings, apartment guides, reviews, and Reddit discussions. Housing guides contain longer sections that benefit from larger chunks, while Reddit discussions contain short opinion-based comments that should remain intact. I used structure-aware chunking instead of fixed character splitting.
For Reddit documents, comments were kept together whenever possible so apartment names and student opinions remained in the same chunk. For listing and guide documents, apartment names, amenities, pricing, and transportation information were kept together to preserve context.

**Final chunk count:** 62 chunks

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:** sentence-transformers/all-MiniLM-L6-v2

**Production tradeoff reflection:**
I selected all-MiniLM-L6-v2 because it runs locally, requires no API key, and provides good semantic search performance for English text. It is fast enough for a student project while still producing useful retrieval results.
For a production system, I would evaluate larger embedding models that provide better semantic understanding, stronger performance on informal review text, multilingual support, and improved handling of apartment names and student slang. I would also compare local models against API-based embeddings to balance cost, latency, and retrieval accuracy.
---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:**

The model is instructed to answer using only the retrieved chunks provided as context. If the retrieved documents do not contain enough information to answer the question, the model is instructed to respond with:
"I don't have enough information in the provided documents."
The model is explicitly prohibited from using outside knowledge.

**How source attribution is surfaced in the response:**

Retrieved source filenames are programmatically attached to every response. The source list is displayed separately in the interface, ensuring citations are always present regardless of the model output.
---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 |What apartments do students recommend near ASU? |Emerson, The Local, Union Tempe, Skye, Vertex, and Oliv are commonly recommended. |Returned "I don't have enough information." |Relevant |Inaccurate |
| 2 |Which apartments should students avoid and why? |West 6, Apollo, Rise, Paseo, Sol, Roosevelt Point, and others due to noise, pests, and management issues. |Correctly identified apartments and summarized reasons. |Relevant |Accurate |
| 3 |What do students say about University House Tempe? |Mixed opinions regarding management, elevators, outages, and affordability. |Returned "I don't have enough information." |Partially Relevant |Inaccurate |
| 4 |What hidden costs do students mention when renting apartments near ASU? |Parking fees, utilities, CAM charges, and other monthly costs. |Correctly identified parking fees, utilities, and extra charges. |Relevant |Accurate |
| 5 |What apartments are considered quiet and close to campus? |Emerson and The Local are commonly described as quieter options. |Returned "I don't have enough information." |Relevant |Partially Accurate |

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

**Question that failed:**

What apartments do students recommend near ASU?

**What the system returned:**

"I don't have enough information in the provided documents."

**Root cause (tied to a specific pipeline stage):**

The retrieval system successfully returned relevant Reddit discussions and housing guides, but the generation stage applied a strict refusal rule. Since recommendations were distributed across multiple comments and chunks rather than being explicitly stated in one chunk, the model declined to generate an answer even though enough evidence existed collectively.

**What you would change to fix it:**

I would reduce the refusal threshold and implement confidence-based aggregation so the model can combine evidence across multiple retrieved chunks before deciding whether enough information exists.

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**

The planning document helped me think through chunking, retrieval, and evaluation before writing code. Having an evaluation plan prepared in advance made it easier to identify retrieval failures and understand where improvements were needed.

**One way your implementation diverged from the spec, and why:**

The original plan relied heavily on automated document collection. Several housing websites blocked scraping attempts, so I manually cleaned and formatted Reddit discussions and review content. These manually curated documents ultimately became some of the most valuable sources in the system.

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:* 
My document sources, chunking strategy, and project requirements.
- *What it produced:*
An ingestion and chunking pipeline using Python and structure-aware chunking.
- *What I changed or overrode:*
I modified the chunking logic so Reddit comments remained intact and apartment details were not split across chunk boundaries.

**Instance 2**

- *What I gave the AI:*
My retrieval architecture, embedding model choice, and ChromaDB requirements.
- *What it produced:*
Embedding and retrieval code using SentenceTransformers and ChromaDB.
- *What I changed or overrode:*
I added source metadata, retrieval reranking, apartment-name matching, and source-type prioritization because initial retrieval favored generic housing guides over apartment-specific discussions.