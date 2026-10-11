import os
import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title='EvidenceRAG', page_icon='📚', layout='wide')
BASE = os.getenv('BACKEND_URL', 'http://127.0.0.1:8000').rstrip('/')


def api(method, path, **kwargs):
    try:
        response = httpx.request(method, BASE + path, timeout=300, **kwargs)
        if response.is_error:
            try:
                detail = response.json().get('detail', response.text)
            except ValueError:
                detail = f'Backend returned HTTP {response.status_code}'
            st.error(str(detail))
            return None
        return response.json() if response.content else {'deleted': True}
    except httpx.RequestError:
        st.error('Cannot reach the backend. Start FastAPI and check BACKEND_URL. The first model download can take several minutes.')
        return None


def render_sources(sources, cited=()):
    for source in sources:
        sid = source.get('source_id', '')
        label = f"[{sid}] " if sid else ''
        page = f" · page {source['page']}" if source['page'] is not None else ''
        used = ' · cited' if sid in cited else ''
        with st.expander(f"{label}{source['document_name']}{page} · similarity {source['score']:.3f}{used}"):
            st.text(source['text'])
            st.caption(f"Chunk {source['chunk_id'][:12]} · characters {source['start']}–{source['end']}")


st.title('EvidenceRAG')
st.caption('Search your documents. Ask with evidence. Inspect every source.')
health = api('GET', '/health')
if not health:
    st.stop()
with st.sidebar:
    st.subheader('Your library')
    st.metric('Documents', health['documents'])
    st.metric('Passages', health['chunks'])
    st.caption('Embedding model: all-MiniLM-L6-v2')
    if health['llm_configured']:
        st.success('LLM configured')
    else:
        st.info('Search works without an LLM. Configure one in .env for generated answers.')
    st.caption('Similarity is a retrieval score, not a probability of correctness.')

manage, search, ask = st.tabs(['Documents', 'Semantic search', 'Ask documents'])
with manage:
    st.subheader('Add documents')
    if 'upload_success' in st.session_state:
        st.success(st.session_state.pop('upload_success'))
    with st.form('upload'):
        files = st.file_uploader('PDF, UTF-8 text, or Markdown · up to 10 MB each',
                                 type=['pdf', 'txt', 'md'], accept_multiple_files=True)
        submitted = st.form_submit_button('Index documents', type='primary')
    if submitted and files:
        successes = 0
        with st.spinner('Extracting text and embedding passages…'):
            for file in files:
                result = api('POST', '/documents', files={'file': (file.name, file.getvalue(), file.type)})
                if result:
                    successes += 1
                    st.success(f"{result['filename']}: {result['page_count']} pages, {result['chunk_count']} chunks")
        if successes:
            st.session_state.upload_success = f'{successes} document(s) indexed successfully.'
            st.rerun()
    documents = api('GET', '/documents')
    if documents:
        st.subheader('Indexed documents')
        for doc in documents:
            left, right = st.columns([5, 1])
            left.write(f"**{doc['filename']}**")
            left.caption(f"{doc['page_count']} pages · {doc['chunk_count']} chunks · {doc['id'][:12]}")
            if right.button('Delete', key=doc['id']):
                if api('DELETE', f"/documents/{doc['id']}"):
                    st.session_state.messages = []
                    st.rerun()
    else:
        st.info('Upload a document to begin. Sample documents are included in the project.')
with search:
    st.subheader('Find relevant passages')
    with st.form('search'):
        query = st.text_input('Search question', placeholder='How can a consumer prevent duplicate processing?')
        top_k = st.slider('Results', 1, 20, 5)
        run = st.form_submit_button('Search', type='primary')
    if run:
        if not query.strip():
            st.warning('Enter a question first.')
        else:
            with st.spinner('Searching…'):
                result = api('POST', '/search', json={'query': query, 'top_k': top_k})
            if result:
                st.caption(f"{result['elapsed_ms']:.1f} ms · {len(result['results'])} passages")
                if result['insufficient_evidence']:
                    st.warning('No strong supporting evidence was found. The threshold is a heuristic.')
                render_sources(result['results'])
with ask:
    st.subheader('Ask your documents')
    st.caption('Each question is independent. Previous turns are displayed but are not sent to the model.')
    if st.button('Clear conversation'):
        st.session_state.messages = []
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    for message in st.session_state.messages:
        with st.chat_message(message['role']):
            if message['role'] == 'user':
                st.write(message['content'])
            else:
                st.write(message['content']['answer'])
                if message['content'].get('warning'):
                    st.caption(message['content']['warning'])
                render_sources(message['content']['sources'], message['content'].get('cited_source_ids', []))
    question = st.chat_input('Ask a question about the indexed documents')
    if question:
        with st.spinner('Retrieving evidence and asking the model…'):
            answer = api('POST', '/ask', json={'query': question})
        if answer:
            st.session_state.messages.extend([{'role': 'user', 'content': question},
                                              {'role': 'assistant', 'content': answer}])
            st.rerun()
