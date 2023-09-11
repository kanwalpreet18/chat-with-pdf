import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings, HuggingFaceInstructEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from htmlTemplates import css, bot_template, user_template
from langchain.llms import HuggingFaceHub
import time
from langchain.callbacks import get_openai_callback
import pinecone

def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 750,
        chunk_overlap = 200,
        length_function = len
    )
    chunks = text_splitter.split_text(text)
    return chunks

def get_vectorstore(text_chunks):
    embeddings = OpenAIEmbeddings()

    # using pinecone
    pinecone.init(
        api_key = os.environ.get("PINCONE_API_KEY"),  # find at app.pinecone.io
        environment = os.environ.get('PINECONE_ENV'),  # next to api key in console
    )

    my_index_name = "topic-modeling"
    index = pinecone.Index(my_index_name)
    # index.delete(delete_all='true')

    vectorstore = Pinecone.from_documents(documents = text_chunks, embedding = embeddings, index_name = my_index_name)

    
    # embeddings = HuggingFaceInstructEmbeddings(model_name="hkunlp/instructor-xl")
    # vectorstore = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
    return vectorstore

def get_conversation_chain(vectorstore):
    llm = ChatOpenAI(model = "gpt-4", temperature = 0)
    # llm = HuggingFaceHub(repo_id="google/flan-t5-xxl", model_kwargs={"temperature":0.5, "max_length":512})

    memory = ConversationBufferMemory(
        memory_key='chat_history', return_messages=True)
    
    conversation_chain = ConversationalRetrievalChain.from_llm(
            llm=llm, 
            retriever=vectorstore.as_retriever(),
            memory=memory
        )
    return conversation_chain

def handle_userinput(user_question):
    response = st.session_state.conversation({'question': user_question})
    st.session_state.chat_history = response['chat_history']

    for i, message in enumerate(st.session_state.chat_history):
        if i % 2 == 0:
            st.write(user_template.replace(
                "{{MSG}}", message.content), unsafe_allow_html=True)
        else:
            st.write(bot_template.replace(
                "{{MSG}}", message.content), unsafe_allow_html=True)

def main():
    load_dotenv()
    st.set_page_config(page_title = "Chat with multiple PDFs",
                       page_icon = ":books:")
    st.write(css, unsafe_allow_html=True)

    if "conversation" not in st.session_state:
        st.session_state.conversation = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = None
    if "token_cb" not in st.session_state:
        token_cb = {'total_tokens': int(0),
            'prompt_tokens': int(0),
            'completion_tokens': int(0),
            'total_cost': float(0)}
        st.session_state.token_cb = token_cb

    st.header("Chat with multiple PDFs :books:")

    user_question = st.text_input("Ask a question to query your PDFs:")
    if user_question:
        with get_openai_callback() as cb:
            handle_userinput(user_question)

            st.session_state.token_cb['total_tokens'] += cb.total_tokens
            st.session_state.token_cb['prompt_tokens'] += cb.prompt_tokens
            st.session_state.token_cb['completion_tokens'] += cb.completion_tokens
            st.session_state.token_cb['total_cost'] += cb.total_cost

            with st.sidebar:
                st.subheader("Token usage")
                st.text(f"Token used: {st.session_state.token_cb['total_tokens']}")
                st.text(f"Prompt tokens: {st.session_state.token_cb['prompt_tokens']}")
                st.text(f"Completion tokens: {st.session_state.token_cb['completion_tokens']}")
                st.text(f"Total cost: ${round(st.session_state.token_cb['total_cost'], 2)}")

    with st.sidebar:
        st.subheader("Your documents")
        pdf_docs = st.file_uploader(
            "Upload your PDFs here and click on 'Process'", accept_multiple_files=True)
        if st.button("Process"):
            with st.spinner("Processing"):
                # get pdf text
                raw_text = get_pdf_text(pdf_docs)
                # get the text chunks
                text_chunks = get_text_chunks(raw_text)
                # create vector store
                vectorstore = get_vectorstore(text_chunks)
                # create conversation chain
                st.session_state.conversation = get_conversation_chain(
                    vectorstore) 
                
if __name__ == '__main__':
    main()
