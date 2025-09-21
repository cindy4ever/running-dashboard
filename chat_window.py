import streamlit as st

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

        # Placeholder until LLM is connected
        response = "🧠 LLM response coming soon: this will answer with personalized insights!"
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.chat_message("assistant").write(response)