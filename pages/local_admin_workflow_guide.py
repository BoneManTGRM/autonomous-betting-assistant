from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Local Admin Workflow Guide", layout="wide")
render_app_sidebar("local_admin_workflow_guide", language_key="local_admin_workflow_guide_language")
require_streamlit_access(st, allow_roles={"admin", "client", "demo"})

st.title("Local Admin Workflow Guide")
st.caption("A local-first workflow for running ABA Signal Pro without a cloud server.")

st.warning("This product is for analytics, proof tracking, and reporting only. It does not guarantee outcomes or returns.")

st.header("Daily operator flow")
st.markdown(
    """
1. Open **Deployment Health** and confirm the app is usable.
2. Run **Pro Predictor Volume** or upload prediction rows.
3. Open **Odds Lock Pro** and review lock candidates.
4. Lock research rows separately from official rows.
5. Let Odds Lock Pro save rows to the existing ledger and local SQLite/CSV fallback.
6. Use **Local First Admin** to verify ledger counts and audit events.
7. Use **Proof ID Verification** to check individual proof rows.
8. Use **Report Studio Local Export** to create client-ready Markdown, HTML, or copy/paste summaries.
9. Use **Local Calibration Dashboard** after rows are graded to review probability calibration.
10. Use **Learning Memory Safety** before training memory from graded rows.
"""
)

st.header("Ledger rules")
st.markdown(
    """
- **Official/client rows** are the only rows that should be used for public proof metrics.
- **Research rows** are useful for testing but should not be mixed into public proof.
- **Quarantine/review rows** should not be promoted until the issue is resolved.
- **Learning-only rows** should not be advertised as forward proof.
- Duplicate rows from one matchup should be reviewed as row-level picks and event-level games separately.
"""
)

st.header("Optional local access")
st.markdown(
    """
No-login remains the default. To enable local access later, set:

```text
ABA_REQUIRE_LOGIN=true
```

Then add local codes through Streamlit secrets or environment variables:

```text
ABA_ADMIN_NAME
ABA_ADMIN_CODE
ABA_CLIENT_NAME
ABA_CLIENT_CODE
ABA_DEMO_NAME
ABA_DEMO_CODE
```

No OAuth, email verification, cloud auth, or separate server is required.
"""
)

st.header("Client report flow")
st.markdown(
    """
1. Use **Report Studio Local Export**.
2. Keep **Public-safe mode** on for client-facing proof.
3. Add a client name and optional background image reference.
4. Download Markdown or HTML.
5. Copy the messenger-ready summary for WhatsApp, Telegram, or email.
6. Do not include private audit fields unless the client is supposed to see them.
"""
)

st.header("Learning safety flow")
st.markdown(
    """
1. Grade rows first.
2. Open **Learning Memory Safety**.
3. Export only rows marked learning-safe.
4. Do not train memory on quarantined, ungraded, missing-probability, missing-price, or bad-audit rows.
5. Keep a backup before replacing memory files.
"""
)
