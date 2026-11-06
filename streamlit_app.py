"""Public demonstration entrypoint for Streamlit Community Cloud."""

import streamlit as st

from dashboard.runtime import DemoRuntime
from dashboard.workbench import render_workbench


@st.cache_resource(show_spinner="Preparing the synthetic security lab…")
def demo_runtime() -> DemoRuntime:
    return DemoRuntime()


runtime = demo_runtime()
render_workbench(base_url=runtime.base_url + "/api/v1", public_demo=True)
