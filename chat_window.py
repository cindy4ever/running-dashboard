import streamlit as st
from chat_backend import send_to_llm

def render_chat(title="💬 Ask Me Anything"):
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.subheader(title)

    # ✅ Display only what's stored — no duplication
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ⌨️ Handle input
    if prompt := st.chat_input("Ask a question about your training..."):
        # Append user input first
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display user input
        with st.chat_message("user"):
            st.markdown(prompt)

        # Call backend and display assistant reply
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response, _ = send_to_llm(prompt, st.session_state.messages)
                except Exception as e:
                    response = f"❌ Error: {e}"
            st.markdown(response)

        # Append assistant reply
        st.session_state.messages.append({"role": "assistant", "content": response})