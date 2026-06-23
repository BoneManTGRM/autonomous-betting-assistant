# Report Studio manual validation checklist

Use this checklist after Streamlit redeploys. It exists because automated smoke tests can validate the report logic offline, but the deployed Streamlit UI still needs browser confirmation.

## Deploy / navigation

1. Reboot the Streamlit app.
2. Confirm the sidebar shows `Report Studio` / `Estudio de Reportes`.
3. Confirm the old duplicate report pages are not shown in the sidebar.
4. Open `Report Studio`.

## Input flows

1. With saved workspace rows enabled, confirm the page loads rows or shows a clear no-rows message.
2. Upload a CSV and confirm rows load.
3. Confirm sport filters work.
4. Confirm max rows works.

## Report modes

1. Consumer Magazine mode renders high-level cards.
2. Tipster Report mode renders the same high-level layer with brand settings.
3. Client-Safe Summary mode renders without technical clutter.
4. Analyst Proof Report mode renders the technical proof table and technical HTML details.

## Fail-closed checks

1. Missing odds rows must show as No Play / Removed and not publish-ready.
2. Invalid odds rows must show as No Play / Removed and not publish-ready.
3. Negative-edge rows must show as No Play / Removed and not publish-ready.
4. Market-baseline-only rows must show as No Play / Removed and not publish-ready.
5. Tennis/ATP/WTA/ITF/Challenger rows must be blocked if unsupported.
6. Positive-edge rows may enter Best Plays only with verified odds, positive EV, and proof/lock evidence.

## Math checks

1. Market probability must equal `1 / decimal_price`.
2. Edge must equal `model_probability - market_probability`.
3. EV must equal `model_probability * decimal_price - 1`.
4. Average model probability must be the average across selected cards, not the first card.
5. `learned_model_probability` must be preferred over market-derived `model_probability`.

## Spanish localization

1. Switch to Spanish.
2. Consumer cards should not show obvious English labels like `Odds`, `Model`, `Market`, `Edge`, `Status`, or `Data check`.
3. Consumer labels should show `Selección`, `Confianza`, `Riesgo`, `Lectura del mercado`, `Por qué importa`, and `Acción recomendada`.
4. Pick text should translate common market phrases such as `Moneyline`, `Game total`, `Over`, and `Under`.

## Exports

1. PDF button renders and downloads a `.pdf` file.
2. HTML button renders and downloads an `.html` file.
3. Markdown button renders and downloads an `.md` file.
4. JSON button renders and downloads a `.json` file.
5. CSV button renders and downloads a `.csv` file.
6. Latest app feed is saved under `data/report_feeds/<workspace>/latest.json`.

## White-label profiles

1. Create or edit a profile.
2. Save the profile.
3. Reload the profile.
4. Confirm brand name, logo URL, tagline, language, title, disclaimer, sports, risk preference, and technical/default audience settings persist.

## Sports context

1. Baseball rows should display available pitching/bullpen/recent-form/park-weather context when the fields exist.
2. Basketball rows should display available pace/rest/injury/matchup/efficiency context when the fields exist.
3. Soccer rows should display available form/home-away/draw-risk/scoring/market-pressure context when the fields exist.
4. Missing context must display as unavailable, not invented.

## Compliance

1. No report should say or imply guaranteed profit.
2. Disclaimers should remain visible in reports.
3. Consumer mode should hide technical fields by default.
4. Analyst mode should preserve model/market/edge/EV/proof/source fields.
