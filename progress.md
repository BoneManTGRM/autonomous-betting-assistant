Plan: ../ABA_SIGNAL_PRO_FINISH_AND_SHIP_PLAN.md

Release constraint: paid sports-data integrations remain installed but unavailable until October. Hybrid mode accepts only operator-attested manual observations with an exact event ID, book, market, price, and current UTC timestamp; missing data stays unavailable.

Task 0: complete — release branch `fix/truthful-page2-parlay-report` is based on `09395854d3e6d41d1dddae45248660be70253faf`; competing report paths were mapped and the central gate was selected.

Task 1: complete — regressions cover the supplied Iraq/France failure, generic uploads, exact manual verification, synthetic-vs-quoted parlay prices, same-game joint-probability blocking, provider credential wiring, and manifest stability.

Task 2: complete — unsupported injury/team/matchup fallbacks and guessed `0.65` parlay correlation were removed. Every export now passes through the central report verification gate. Paid API adapters remain available for reactivation when keys return.

Task 3: complete — Page 2 now produces ranked 2-leg and 3-leg recommendations with individual leg event/market/price/book/source/time/probability, exact leg-matched combined quotes, joint probability, implied probability, EV, minimum acceptable price, quarter-Kelly bankroll fraction, profit profile, correlation basis, diagnostics, and cancellation conditions. Arithmetic product prices without an exact combined quote remain conditional watchlists.

Task 4: complete locally — all 1,576 tests passed, compileall passed, `git diff --check` passed, and the final two-page PDF was rendered and visually inspected. A Pillow multi-page raster defect found during inspection was fixed by losslessly snapshotting each page before PDF assembly. Page 1 and Page 2 now use one parlay snapshot per render; brand name, report titles, language, header logo, and full-page background remain presentation-only customizations. Demonstration fixtures are explicitly blocked from rendering as current `PLAY` advice.

Task 5: in progress — create the scoped commit/PR, obtain exact-SHA CI evidence, integrate through the protected workflow, identify the deployment target, and rerun NICO only when its GitHub evidence path can assess the exact release SHA.
