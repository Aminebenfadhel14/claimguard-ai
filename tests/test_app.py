from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_academic_interface_loads():
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app/Home.py')).run(timeout=30)
    assert not app.exception
    assert len(app.tabs)==4
