# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

<!-- What domain did you choose? Why is this knowledge valuable and hard to find through official channels? -->

--- ASU Off-campus housing experiences is my domain. As an international student, when I first planned my trip, my main focus was on where to stay, but me and my friends did not have a clear channel to learn what the housing options were actually like. We searched everything on Google and eventually finalized a place, but having a searchable system with student experiences would help new students choose housing based on their own preferences, budget, commute, and comfort level. This knowledge is hard to find through official channels because apartment websites mostly show marketing information, while the most useful details for students often come from reviews, Reddit discussions, sublease posts, and unofficial guides. Those sources capture issues like noise, maintenance, pests, parking, walkability, and how far a place really feels from campus.

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
| 1 |ASU Official Website |This has the places and their location,walk time to campus with email,phone number. |https://offcampushousing.asu.edu |
| 2 |College Pads |this has info and map similar to asu official one but has availability with date |https://www.rentcollegepads.com/off-campus-housing/asu/search |
| 3 |uhomes.com |This has the offers,facilities and more details about the spaces and different transportation timings. |https://en.uhomes.com/us/tempe |
| 4 |Birdeye Reviews |this has the reviews from residents and students about the places. Large dataset |https://reviews.birdeye.com/the-district-on-apache-161368555711655 |
| 5 |rate my apartments |This has 700+ results just around ASU |https://www.ratemyapartments.com/ratings/az/arizona-state-university-at-the-tempe-campus |
| 6 |Apartmentlist.com |This has the quick view and availabilty option |https://www.apartmentlist.com/off-campus-housing/az/asu-apartments-for-rent |
| 7 | Off-Campus Universe guide | This has the step by step guide student who don't know what to do can follow. | https://www.offcampus-universe.com/post/apartments-near-arizona-state-university-best-off-campus-housing-for-asu-students |
| 8 | Off-Campus Universe guide | This has the step by step guide student who don't know what to do can follow. | https://www.offcampus-universe.com/post/asu-off-campus-housing-guide-apartments-houses-and-subleases-in-tempe |
| 9 |Reddit search |This has the discussions about the off campus housing and places specifically about Apartments to avoid|https://www.reddit.com/r/ASU/search/?q=apartments |
| 10 |Reddit search |This has the discussions about the off campus housing and places specifically do any student apartments not suck|https://www.reddit.com/r/ASU/search/?q=apartments |
| 11 |Reddit search |athis has the discussions about the off campus housing and places specifically Housing takeover megathread |https://www.reddit.com/r/ASU/search/?q=apartments |
| 12 |Reddit search |athis has the discussions about the off campus housing and places specifically what apertments are good in tempe near ASU |https://www.reddit.com/r/ASU/search/?q=apartments |

---

## Chunking Strategy

<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size:** 300-450 tokens

**Overlap:** 60

**Reasoning:**
My documents are a mix of short listing pages and long Reddit comment threads. For listing pages, most useful information is concentrated in a small amount of text, so smaller chunks help retrieval stay precise. For Reddit threads, the apartment name, price, commute time, and user opinion often appear in separate comments, so slightly larger chunks with overlap reduce the risk of splitting a useful recommendation across chunk boundaries.so i choose the recursive chucking strategy.
I will chunk by structure first, not just by raw length:
For apartment/listing pages: split by property section, amenity section, or listing card.
For Reddit threads: split by comment blocks, keeping each top-level comment and its reply chain together when possible.
For guides: split by heading or subsection.
---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model:** all-MiniLM-L6-v2

**Top-k:** 6

**Production tradeoff reflection:**
I am using all-MiniLM-L6-v2 because it runs locally, is fast, and is strong enough for a small-to-medium student project. It does not require API costs and works well for English text, which fits my dataset. If I were deploying this for real users with no cost constraint, I would compare stronger embedding models with better semantic matching on noisy review text, longer-context support, and potentially better retrieval for informal language. I would also consider multilingual support because international students may search in more than one language, and I would compare local embeddings versus API-based embeddings based on latency, cost, and privacy.
For retrieval, I will use semantic similarity search in ChromaDB. I will retrieve the top 6 chunks for each query and include their source metadata in the prompt so the model can cite which documents it used.

---

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

| # | Question | Expected answer |
|---|----------|-----------------|
| 1 |What apartments do students mention as good options near ASU? |Students mention Emerson, Union Tempe, The Local, Oliv, Skye, The Cameron, Vertex, and Lakeside Drive as positive options in different contexts. |
| 2 |Which apartments do students most often say to avoid and why? |West 6, Apollo, Paseo on University, Sol, Oliv (in some comments), University House, and Roosevelt Point are criticized for noise, pests, poor management, or maintenance issues. |
| 3 |What hidden costs do students mention for luxury apartments near campus? |Students mention parking fees, CAM charges, utilities, and other add-on costs that can make an advertised rent much higher than the base price. |
| 4 |Which apartments do students say are walkable to campus and still relatively quiet? |Emerson, The Local, Union Tempe, and some units at Oliv or Skye are mentioned as walkable or close, while Emerson and The Local are often described as quieter than more party-oriented buildings. |
| 5 |What does the Housing discussions say about University House Tempe? |Multiple lease posts mention University House being very close to ASU, fully furnished, and around the $1,059–$1,200/month range depending on unit type and lease terms. |

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1.Reddit comments are noisy and repetitive, so retrieval may surface irrelevant replies or duplicate advice unless the chunking keeps only meaningful comment blocks.

2.Some sources mix marketing language with real student experiences. If retrieval pulls only promotional text, the answer may sound grounded but still miss the complaints and tradeoffs that students actually care about.

---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->

     Document Ingestion\nBeautifulSoup / manual Reddit text files --> Cleaning + Chunking\nrule-based section splitting --> Embedding + Vector Store\nsentence-transformers all-MiniLM-L6-v2 + ChromaDB --> Retrieval\nsemantic search top-k=6 --> Generation
---

## AI Tool Plan

<!-- For each part of the pipeline below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, which requirements)
     - What you expect it to produce
     - How you'll verify the output matches your spec

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Chunking Strategy section and ask it to implement chunk_text()
     with my specified chunk size and overlap" is a plan. -->

**Milestone 3 — Ingestion and chunking:**

I will use ChatGPT or Claude to help build the ingestion and chunking pipeline. I will extract text from housing websites using BeautifulSoup and manually collect Reddit discussions because they cannot be reliably extracted in a structured format. Using my chunk size and overlap settings, I will ask the AI tool to generate the chunking logic. Chunking will follow document structure rather than fixed character counts. Reddit comments will remain intact whenever possible, and apartment details such as names, prices, amenities, and transportation information will stay within the same chunk. I will verify the output by ensuring comments are not split across chunks and apartment information remains grouped together with its related details.

**Milestone 4 — Embedding and retrieval:**
I will use ChatGPT or Claude to help wire up sentence-transformers and ChromaDB. I will provide the Retrieval Approach section, the source list, and a few example queries, and ask it to build embedding and search functions that return the top 6 most relevant chunks with metadata. I will verify the output by running my 5 evaluation questions and checking whether the retrieved chunks actually contain the expected apartment names, prices, and complaints.

**Milestone 5 — Generation and interface:**

I will use Claude or ChatGPT to help write the answer-generation prompt and the interface layer. I will give it the evaluation plan and ask it to generate a response only from retrieved chunks, with explicit source attribution in the final answer. For the interface, I will keep it simple and build either a CLI or a minimal Streamlit app so it is easy to demonstrate. I will verify that the response includes citations, does not invent information outside the retrieved text, and answers the user’s question in plain language.