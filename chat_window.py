import streamlit as st
from chat_backend import send_to_llm

def render_chat(title="💬 Ask Me Anything"):
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.subheader(title)
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    prompt = st.chat_input("Ask a question about your training...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        # ✅ Call the actual LLM backend
        with st.spinner("Thinking..."):
            try:
                response, _ = send_to_llm(prompt, st.session_state.messages)
            except Exception as e:
                response = f"❌ Error: {e}"

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.chat_message("assistant").write(response)