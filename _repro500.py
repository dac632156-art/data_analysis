import sys, traceback
sys.path.insert(0, "backend")
from backend.services.session_manager import manager

SID = "fd22be77-80d3-4867-9619-5e6259ea8826"
try:
    session = manager.get_session(SID)
    print("get_session OK, datasets attr:", type(getattr(session, "datasets", None)))
    ds = manager.get_datasets(SID)
    print("get_datasets OK:", ds)
    print("uploaded_bytes:", getattr(session, "uploaded_bytes", "N/A"))
except Exception as e:
    traceback.print_exc()
    print("REPRO-EXC:", repr(e))
