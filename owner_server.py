"""Railway-only owner-authenticated entrypoint; legacy entrypoints stay unchanged.

Start: python -m streamlit run owner_server.py --server.address=0.0.0.0 --server.port=$PORT
"""
from pathlib import Path

import streamlit as st
from starlette.middleware import Middleware

from owner_auth import OwnerAuthMiddleware

if st.__version__ != '1.66.1':
    raise RuntimeError('Owner entrypoint requires the reviewed Streamlit 1.66.1 pin.')

app = st.App(str(Path(__file__).resolve().with_name('streamlit_app.py')),
             middleware=[Middleware(OwnerAuthMiddleware)])
