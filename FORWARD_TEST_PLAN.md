# Forward Test Plan

## Current boundary

The Forward Test Tracker now prepares and reviews supplied evidence. It does not
certify a forward test, a win rate, profitability, an independent timestamp, or
source authenticity. Historical `official_locked` labels are not independent
proof. Existing historical records and learned weights remain unchanged.

## Minimum operator workflow

1. Open **Advanced → Forward Test Tracker**. Declare the population, selection
   policy, exclusions and frozen baseline before seeing outcomes.
2. Download the blank preparation JSON. Supply original model probabilities and
   versions, one event identity namespace, exact market/selection identities and
   settlement rules, source-availability times and fresh observed odds. Missing
   evidence must stay missing; do not backfill it from confidence or results.
3. Paste the completed JSON and prepare a packet **before event start**. Download
   and retain the exact original packet and blank linked result receipts. The
   preparation clock and hash are only local consistency checks. They are not an
   independent commitment and do not start an authenticated forward test.
4. Obtain a separately controlled pre-event timestamp for the exact packet and
   independently reconcile event identity, source availability and model
   artifacts. This integration is not implemented by this workflow. No purchase,
   new credential or external publication is performed automatically.
5. After a source reports the event final, retain the source document/receipt,
   its SHA256, URL, observation time, reviewer reference and settlement reason.
   A string, URL, `final` assertion or supplied hash alone is not authentication.
6. Paste the original packet and subsequent receipts into Review. All original
   cohort rows remain visible, including pending, void, rejected and conflicting
   evidence. Duplicate/revised receipts never silently replace prior receipts.
   Download and retain the full review. Corrected evidence must retain the old
   originals for independent reconciliation.

This page is session-only and download-only: it does not establish persistent
server storage or survival across a restart. Keep downloaded originals. Changing
input hides the old result; it cannot silently relabel it as the new result.

## When accuracy evaluation becomes meaningful

Only a genuinely prospectively registered, independently verified cohort can
support a real forward-performance claim. Count distinct events and related
selections honestly; a large number of correlated rows is not independent
sample evidence. Preserve all exclusions and pending/void/rejected coverage.
Never count unresolved outcomes as wins or infer profit from stake/units.

The separate offline evaluator's existing minimum gates remain unchanged:
50 training events, 100 holdout events and 20 holdout decision-day blocks. These
are engineering admission gates, not guarantees of statistical power or profit.
Its holdout is not protected merely because an uploaded manifest calls it one.
No training or promotion is enabled by this preparation page.

## Español (México)

Usa **Avanzado → Seguimiento prospectivo** para preparar un paquete antes del
inicio de los eventos y conservar el archivo original. Declara de antemano la
población, selección, exclusiones y referencia. No reconstruyas probabilidades
faltantes a partir de etiquetas de confianza, cuotas o resultados.

La hora local, una URL y una huella SHA256 no prueban la existencia previa ni la
autenticidad de los datos. Se requiere una constancia independiente del paquete
exacto y revisión independiente de las fuentes. Esa integración no está incluida.
Los comprobantes posteriores deben conservar la identidad exacta del evento,
mercado y selección, la fuente final, sus fechas y la explicación de liquidación.

La revisión conserva toda la cohorte, incluidos pendientes, anulaciones y
conflictos. Ninguna fila se vuelve «verificada» automáticamente; no se certifican
aciertos ni rentabilidad. Descarga y conserva los originales: la página no guarda
el paquete en disco ni comprueba su persistencia. El historial, los pesos y los
requisitos de aceptación no cambian.
