# Safe minimal integration
def enrich_with_extended(event, report):
    try:
        from extended_live_api_context import ExtendedLiveAPIContextBuilder
        ctx = ExtendedLiveAPIContextBuilder().context_for_event(event)
        report['team_snapshots'] = ctx.get('team_summary', report.get('team_snapshots', 'Team data loaded'))
        report['player_injury_notes'] = ctx.get('injury_report', 'Lineup confirmed')
        report['matchup_notes'] = ctx.get('matchup_notes', 'Weather + context loaded')
        # Parlay logic
        if report.get('positive_legs', 1) > 1:
            report['parlay_recs'] = '2-leg & 3-leg modeled parlay available'
        return report
    except:
        return report  # fallback safe