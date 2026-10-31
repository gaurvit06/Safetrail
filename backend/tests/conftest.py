import os
import pathlib
import sys
import tempfile

_tmp = tempfile.mkdtemp(prefix="safetrail-test-")
os.environ["DB_PATH"] = os.path.join(_tmp, "test.db")
os.environ["PRUNE_API_KEY"] = ""
os.environ["PRUNE_PUBLIC_API_KEY"] = ""
os.environ["MODEL_SMALL"] = "small-model"
os.environ["MODEL_LARGE"] = "large-model"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.seeddata import seed_db  # noqa: E402

init_db()
with Session(engine) as _s:
    seed_db(_s)


@pytest.fixture(autouse=True)
def clean_db():
    from app import models
    from app.ai import prune_client

    prune_client.reset_state()
    with Session(engine) as s:
        for m in (models.SosEvent, models.Incident, models.Ping, models.Trip, models.Pass, models.AiJob,
                  models.LlmCall, models.SafetyCheck, models.CheckResponse, models.EventLog, models.BreakItAttempt,
                  models.SmsInbound):
            for row in s.exec(select(m)).all():
                s.delete(row)
        s.commit()
    yield


@pytest.fixture
def s():
    with Session(engine) as session:
        yield session
