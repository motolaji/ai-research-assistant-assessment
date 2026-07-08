from pathlib import Path
from app.data_store import DataStore

store = DataStore(Path("mock-data"))

def test_get_project_by_id_known():
    project = store.get_project_by_id("PRJ001")
    assert project["title"] == "Early Detection of Type 2 Diabetes"

def test_get_project_by_id_unknown_returns_none():
    assert store.get_project_by_id("PRJ999") is None

def test_search_datasets_keyword_matches_description():
    results = store.search_datasets(keyword="diabetes")
    ids = [d["id"] for d in results]
    assert "DS001" in ids

def test_search_datasets_restricted_filter():
    results = store.search_datasets(restricted=False)
    assert all(d["restricted"] is False for d in results)

def test_search_datasets_min_records_strictly_greater():
    results = store.search_datasets(min_records=20000)
    assert all(d["records"] > 20000 for d in results)

def test_projects_for_dataset():
    projects = store.projects_for_dataset("DS001")
    assert any(p["id"] == "PRJ001" for p in projects)

def test_get_query_results_count():
    assert store.get_query_results("DS002")["count"] == 2