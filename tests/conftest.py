import pytest
import tempfile
import os


@pytest.fixture
def tmp_db_path(tmp_path):
    return str(tmp_path / "test_jobs.db")
