"""
query.py - grounded generation for "The Unofficial Guide" (UIUC off-campus housing RAG).

Pipeline: retrieve() (embed.py) -> build a numbered, source-tagged context -> Groq
openai/gpt-oss-120b with a hard grounding prompt -> programmatic source attribution.
Out-of-scope questions are refused both before the LLM (a weak-match distance gate) and by
the grounding prompt itself.

Run `python query.py` for the grounding test harness. Needs GROQ_API_KEY in .env.
"""

import os
import sys

from dotenv import load_dotenv
from groq import Groq

from embed import retrieve

load_dotenv()

MODEL = "openai/gpt-oss-120b"
WEAK_MATCH_DISTANCE = 0.8          # cosine distance; backstop for "effectively unrelated"
REFUSAL = "I don't have enough information on that."

# Hard grounding: the second sentence is the clause that forbids outside knowledge.
SYSTEM_PROMPT = (
    "You are a factual assistant for off-campus housing at the University of Illinois "
    "Urbana-Champaign. Answer the question using ONLY the information in the provided "
    "context. Do not use any outside or prior knowledge. If the context does not contain "
    f"enough information to answer, respond with exactly: \"{REFUSAL}\" Do not guess or "
    "fill gaps from general knowledge. Do not mention the context or sources in your answer."
)

_client = None


def get_client():
    """The Groq client, created once and reused."""
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


def _format_context(chunks):
    """Number the retrieved chunks and tag each with its source_file so the model sees
    provenance. This text is the ONLY material the model is allowed to use."""
    return "\n\n".join(
        f"[{i}] (source: {c['metadata']['source_file']})\n{c['text']}"
        for i, c in enumerate(chunks, 1)
    )


def ask(question, k=5):
    """Retrieve -> grounded generation -> programmatic attribution.
    Returns {"answer": str, "sources": list[str], "chunks": list[dict]}."""
    chunks = retrieve(question, k=k)

    # Refusal short-circuit: nothing retrieved, or the best match is effectively unrelated.
    # Catches out-of-scope questions before the model can improvise.
    if not chunks or chunks[0]["distance"] > WEAK_MATCH_DISTANCE:
        return {"answer": REFUSAL, "sources": [], "chunks": chunks}

    user_msg = f"Context:\n{_format_context(chunks)}\n\nQuestion: {question}"
    response = get_client().chat.completions.create(
        model=MODEL,
        temperature=0,                              # deterministic, less embellishment
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    answer = response.choices[0].message.content.strip()

    # Sources come from the retrieved chunks' metadata, never from the model's text
    # (order-preserving dedupe). Suppressed entirely when the model refused.
    sources = list(dict.fromkeys(c["metadata"]["source_file"] for c in chunks))
    if answer == REFUSAL:
        sources = []

    return {"answer": answer, "sources": sources, "chunks": chunks}


# Grounding test harness: Q1 fact, Q4 reviews, Q5 legal stress test, out-of-scope refusal.
TEST_QUESTIONS = [
    "What is the monthly rent for a 2 bedroom unit at Legacy 202?",
    "What do students say about management at Pacifica on Green?",
    "How long does a landlord have to return a security deposit under the Urbana ordinance?",
    "What's the best dining hall on campus?",
]


def main():
    try:                                            # render curly quotes on Windows console
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    for q in TEST_QUESTIONS:
        result = ask(q)
        print("=" * 78)
        print(f"Q: {q}")
        print(f"A: {result['answer']}")
        print(f"Sources: {', '.join(result['sources']) if result['sources'] else '(none)'}")
        print()


if __name__ == "__main__":
    main()
