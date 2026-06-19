# Mobile-safe input path

The mobile Safari/Streamlit file picker and some button controls have been unreliable during testing.

For the core testing flow, use text-entry or CSV paste instead of buttons:

1. What Are the Odds
   - Enter a single game manually, or paste CSV text.
   - The page auto-saves rows when required fields are present.
   - No Analyze button, file-upload button, or download button is required.

2. Threshold Optimizer
   - Paste graded CSV text.
   - The optimizer auto-runs when valid CSV text is present.
   - No Run, upload, or download button is required.

3. Pro Predictor and Odds Lock Pro
   - Continue using existing controls.
   - If mobile buttons fail, use the direct/manual hold path where available.
