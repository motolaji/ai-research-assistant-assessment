import json
from pathlib import Path

class DataStore:
    
    """
    A simple in-memory data store for storing and retrieving data. (switch to a database later)
    """
        
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

        #ingestion: load raw files 
        self.projects = self._load("projects.json")
        self.datasets = self._load("datasets.json")
        self.researchers = self._load("researchers.json")
        self.query_results = self._load("sample_query_results.json")

        # Index built once at startup ... O(1) id lookups.

        self.projects_by_id = {p["id"]: p for p in self.projects}
        self.datasets_by_id = {d["id"]: d for d in self.datasets}
        self.researchers_by_username = {r["username"]: r for r in self.researchers}

    #Load json data from file
    def _load(self,filename: str):
        path = self.data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f" Required File {filename} not found in data directory.")
        with open(path, encoding="utf-8",) as f:
            return json.load(f)    

    def get_project_by_id(self, project_id: str) -> dict | None:
        return self.projects_by_id.get(project_id.strip().upper())
    
    def get_dataset_by_id(self, dataset_id: str) -> dict | None:
        return self.datasets_by_id.get(dataset_id.strip().upper())
    
    def get_query_results(self, dataset_id: str) -> dict | None:
        return self.query_results.get(dataset_id.strip().upper())
    
    def get_researcher_by_username(self, username: str) -> dict | None:
        return self.researchers_by_username.get(username.strip().lower())
    
    def get_all_projects(self) -> list[dict]:
        return self.projects
    
    def get_all_datasets(self) -> list[dict]:
        return self.datasets
    
    #Search 

    def search_projects(self, status: str | None = None, keyword: str | None = None) -> list[dict]:
        results = self.projects

        if status is not None:
            results = [p for p in results if p["status"].lower() == status.lower()]

        if keyword is not None:

            kw = keyword.lower()
            results = [
                p for p in results
                if kw in f"{p['title']} {p['organisation']}".lower()
            ]

        return results
    
    def search_datasets(self, keyword: str | None = None, restricted: bool | None = None, min_records: int | None = None) -> list[dict]:
        results = self.datasets

        if keyword is not None:
            kw = keyword.lower()
            results = [
                d for d in results
                if kw in f"{d['name']} {d['description']}".lower()
            ]

        if restricted is not None:
            results = [d for d in results if d["restricted"] == restricted]

        if min_records is not None:
            results = [d for d in results if d["records"] >= min_records]
            

        return results
    
    def search_researchers(self, role: str | None = None) -> list[dict]:
        results = self.researchers

        if role is not None:
            results = [r for r in results if r["role"].lower() == role.lower()]

        return results


    def datasets_for_project(self, project_id: str) -> list[dict]:
        project = self.get_project_by_id(project_id)
        if project is None:
            return []
        #dataset_ids = project.get("dataset_ids", [])
        return [d for d in (self.get_dataset_by_id(ds_id) for ds_id in project["datasets"]) if d is not None]
    
    def projects_for_dataset(self, dataset_id: str) -> list[dict]:
        ds_id = dataset_id.strip().upper()
        return [p for p in self.projects if ds_id in p["datasets"]]
