from __future__ import annotations

import gradio as gr

from query import ask


def handle_query(question: str):
    question = (question or "").strip()
    if not question:
        return "Please enter a question.", ""

    result = ask(question)

    answer = result["answer"]
    sources = result["sources"]

    if sources:
        source_text = "\n".join(f"• {s}" for s in sources)
    else:
        source_text = "No sources returned."

    return answer, source_text


with gr.Blocks(title="The Unofficial Guide") as demo:
    gr.Markdown("# The Unofficial Guide\nAsk about ASU off-campus housing.")

    with gr.Row():
        inp = gr.Textbox(
            label="Your question",
            placeholder="Example: What do students say about University House Tempe?",
            lines=2,
        )

    ask_btn = gr.Button("Ask")
    answer = gr.Textbox(label="Answer", lines=10)
    sources = gr.Textbox(label="Retrieved from", lines=6)

    ask_btn.click(handle_query, inputs=inp, outputs=[answer, sources])
    inp.submit(handle_query, inputs=inp, outputs=[answer, sources])

if __name__ == "__main__":
    demo.launch(share=True)