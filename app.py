"""
app.py - minimal Gradio UI for "The Unofficial Guide".

Run `python app.py`, then open http://localhost:7860. Each question is answered by
query.ask(), which grounds the answer in retrieved chunks and attaches their sources.
"""

import gradio as gr

from query import ask


def handle_query(question):
    """Run one question through the RAG pipeline; return (answer, formatted sources)."""
    if not question or not question.strip():
        return "Please enter a question.", ""
    result = ask(question)
    sources = result["sources"]
    sources_text = "\n".join(f"• {s}" for s in sources) if sources else "(no sources)"
    return result["answer"], sources_text


with gr.Blocks(title="The Unofficial Guide") as demo:
    gr.Markdown(
        "# The Unofficial Guide\n"
        "UIUC off-campus housing — grounded answers from listings, resident reviews, "
        "and the Urbana Landlord-Tenant Ordinance."
    )
    inp = gr.Textbox(label="Your question", placeholder="e.g. Are pets allowed at Legacy 202?")
    btn = gr.Button("Ask", variant="primary")
    out = gr.Textbox(label="Answer", lines=6)
    src = gr.Textbox(label="Retrieved from", lines=4)

    btn.click(handle_query, inputs=inp, outputs=[out, src])
    inp.submit(handle_query, inputs=inp, outputs=[out, src])


if __name__ == "__main__":
    demo.launch()
