"""Real Streamlit same-process rendering regressions, with no provider actions."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]
ENTRYPOINTS=['streamlit_app.py','app.py','app_streamlit.py','main.py','run.py','autonomous-betting-agent.py']

def assert_home(app, language='en'):
 assert not app.exception
 assert [x.value for x in app.title]==['ABA Signal Pro']
 expected='Use the Tools menu' if language=='en' else 'Usa el menú Tools'
 assert any(expected in str(x.value) for x in app.info)
 assert any(x.key=='aba_radio_global_language' for x in app.radio)

@pytest.mark.parametrize('entry',ENTRYPOINTS)
@pytest.mark.parametrize('scenario',['rerun','language','return','second_session'])
def test_home_rendered_on_every_execution(entry,scenario):
 app=AppTest.from_file(str(ROOT/entry)).run(timeout=60)
 assert_home(app)
 app.session_state['SYNTHETIC_HOME_SENTINEL']={'unchanged':True}
 if scenario=='rerun':
  app.run(timeout=60);assert_home(app)
 elif scenario=='language':
  app.radio(key='aba_radio_global_language').set_value('Español').run(timeout=60)
  assert_home(app,'es')
  app.radio(key='aba_radio_global_language').set_value('English').run(timeout=60)
  assert_home(app)
 elif scenario=='return':
  app.switch_page('pages/pro_predictor_volume.py').run(timeout=60)
  assert not app.exception
  app.switch_page(entry).run(timeout=60)
  assert_home(app)
 else:
  second=AppTest.from_file(str(ROOT/entry)).run(timeout=60)
  assert_home(second)
  assert 'SYNTHETIC_HOME_SENTINEL' not in second.session_state
  second.run(timeout=60);assert_home(second)
 assert app.session_state['SYNTHETIC_HOME_SENTINEL']=={'unchanged':True}

@pytest.mark.parametrize('entry',ENTRYPOINTS)
def test_home_reruns_preserve_unrelated_query_parameters(entry):
 app=AppTest.from_file(str(ROOT/entry))
 app.query_params['synthetic_home_probe']=['keep']
 app.run(timeout=60);assert_home(app)
 app.run(timeout=60);assert_home(app)
 app.radio(key='aba_radio_global_language').set_value('Español').run(timeout=60)
 assert_home(app,'es')
 assert app.query_params['synthetic_home_probe']=='keep'

@pytest.mark.parametrize('entry',ENTRYPOINTS)
def test_repeated_home_with_synthetic_provider_keys_remains_local(entry,monkeypatch):
 for key in ['THE_ODDS_API_KEY','ODDS_API_KEY','WEATHERAPI_KEY','NEWSAPI_KEY','API_FOOTBALL_KEY','SPORTSDATAIO_API_KEY','PERPLEXITY_API_KEY','BALLDONTLIE_API_KEY','OPENAI_API_KEY']:
  monkeypatch.setenv(key,'SYNTHETIC_NOT_A_REAL_KEY')
 app=AppTest.from_file(str(ROOT/entry)).run(timeout=60);assert_home(app)
 app.run(timeout=60);assert_home(app)
 second=AppTest.from_file(str(ROOT/entry)).run(timeout=60);assert_home(second)
