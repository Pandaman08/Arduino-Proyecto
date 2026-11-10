"""Experiment transitions must use device confirmations, never bridge receipts."""
from pathlib import Path
import shutil


def test_streamlit_starts_experiment_only_on_matching_device_confirmation(tmp_path, monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    import src.persistence.database as database_module
    import src.ml.model_manager as ml
    import src.mqtt.streamlit_adapter as adapter
    from src.config import MODEL_PATH, DATASET_PATH
    from src.persistence import ExperimentManager, SQLiteDatabase

    class Subscriber:
        is_connected = True
        def __init__(self): self.messages = []
        def poll(self):
            result, self.messages = self.messages, []
            return result
        def stop(self): pass

    subscriber = Subscriber()
    database_path = tmp_path / 'experiments.db'
    model_path = tmp_path / 'model.pkl'
    if MODEL_PATH.exists(): shutil.copy2(MODEL_PATH, model_path)
    load_predictor = ml.load_or_train_predictor
    monkeypatch.setattr(database_module, 'EXPERIMENTS_DB_PATH', database_path)
    monkeypatch.setattr(ml, 'load_or_train_predictor', lambda: load_predictor(model_path, DATASET_PATH))
    monkeypatch.setattr(adapter, 'create_optional_streamlit_subscriber', lambda: (subscriber, 'conectado'))
    st.cache_resource.clear()
    try:
        at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30).run()
        assert not at.exception
        manager = ExperimentManager(SQLiteDatabase(database_path))
        experiment = manager.create_experiment(grain_type='cafe', phase='despues', origin='real', thermal_reference_c=30)
        pending = {'request_id': 'matching-id', 'node_id': 'secador_01', 'command': 'MODO:CONTROL', 'action': 'start', 'experiment_id': experiment.id}
        at.session_state['pending_command'] = pending
        response = {'_topic': 'secado/secador_01/ack', 'node_id': 'secador_01', 'request_id': 'matching-id', 'command': 'MODO:CONTROL', 'accepted': True}
        for extra in [
            {'source': 'bridge', 'phase': 'forwarded'},
            {'source': 'firmware', 'phase': 'applied', 'correlated': False},
            {'source': 'firmware', 'phase': 'applied', 'correlated': True, '_retained': True},
            {'source': 'firmware', 'phase': 'applied', 'correlated': True, 'node_id': 'otro'},
        ]:
            subscriber.messages.append(response | extra)
            at.run()
            assert not at.exception
            assert manager.get_experiment(experiment.id).status == 'preparado'
        subscriber.messages.append(response | {'source': 'firmware', 'phase': 'applied', 'correlated': True})
        at.run()
        assert not at.exception
        assert manager.get_experiment(experiment.id).status == 'ejecutando'
        assert at.session_state['pending_command'] is None
        at.session_state['pending_command'] = pending | {'action': 'pause', 'command': 'PARAR'}
        subscriber.messages.append(response | {'command': 'PARAR', 'accepted': False, 'source': 'bridge'})
        at.run()
        assert at.session_state['pending_command'] is None
        assert manager.get_experiment(experiment.id).status == 'ejecutando'
        at.session_state['pending_command'] = pending | {'created_at': '1970-01-01T00:00:00Z'}
        at.run()
        assert at.session_state['pending_command'] is None
        assert 'resultado desconocido' in at.session_state['last_error']
    finally:
        st.cache_resource.clear()
