from __future__ import annotations

import os
import tempfile

import pytest

from berkas.app import create_app
from berkas.config import Settings


@pytest.fixture()
def settings(tmp_path) -> Settings:
    return Settings(
        database_url="sqlite:///" + os.path.join(tmp_path, "test.db").replace("\\", "/"),
        upload_folder=os.path.join(tmp_path, "uploads"),
        max_workers=2,
        api_token="",
        environment="test",
        ai_provider="none",
        groq_api_key="",
        openai_api_key="",
    )


@pytest.fixture()
def app(settings):
    application = create_app(settings)
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def tmp_dir():
    return tempfile.mkdtemp()
