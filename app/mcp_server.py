from app.data_store import DataStore
from app.governance import GovernanceContext, PolicyChain
from app.tool_schemas import TOOL_SCHEMAS


def discover_projects(store: DataStore, status: str | None = None, keyword: str | None = None) -> dict:
    results = store.search_projects(status=status, keyword=keyword)
    return {"projects": results, "count": len(results)}

def get_project(store: DataStore, project_id: str) -> dict:
    project = store.get_project_by_id(project_id)
    if project is None:
        return {"error": f"Project with ID '{project_id}' not found."}
    return project

def search_datasets_tool(store: DataStore, keyword: str | None = None, restricted: bool | None = None, min_records: int | None = None) -> dict:
    results = store.search_datasets(keyword=keyword, restricted=restricted, min_records=min_records)
    return {"datasets": results, "count": len(results)}

def get_dataset_metadata(store: DataStore, dataset_id: str) -> dict:
    dataset = store.get_dataset_by_id(dataset_id)
    if dataset is None:
        return {"error": f"Dataset with ID '{dataset_id}' not found."}
    return dataset

def get_researcher(store: DataStore, username: str | None = None, role: str | None = None) -> dict:
    if username is not None:
        researcher = store.get_researcher_by_username(username)
        if researcher is None:
            return {"error": f"Researcher with username '{username}' not found."}
        return researcher
    else:
        results = store.search_researchers(role=role)
        return {"researchers": results, "count": len(results)}
    
def execute_query(store: DataStore, chain: PolicyChain, dataset_id: str, researcher: dict | None, trace_id: str) -> dict:
    dataset = store.get_dataset_by_id(dataset_id)
    if dataset is None:
        return {"error": "Dataset not found"}

    raw_result = store.get_query_results(dataset_id)
    if raw_result is None:
        return {"error": "No query results available for this dataset"}

    context = GovernanceContext(
        tool_name="execute_query",
        args={"dataset_id": dataset_id},
        dataset=dataset,
        researcher=researcher,
        trace_id=trace_id,
    )
    return chain.apply(raw_result, context)    

# dispatcher function for agent py

def dispatch_tool(
    tool_name: str,
    tool_args: dict,
    store: DataStore,
    chain: PolicyChain,
    researcher: dict | None,
    trace_id: str,
) -> dict:
    if tool_name == "discover_projects":
        return discover_projects(store, **tool_args)
    if tool_name == "get_project":
        return get_project(store, **tool_args)
    if tool_name == "search_datasets":
        return search_datasets_tool(store, **tool_args)
    if tool_name == "get_dataset_metadata":
        return get_dataset_metadata(store, **tool_args)
    if tool_name == "execute_query":
        return execute_query(store, chain, researcher=researcher, trace_id=trace_id, **tool_args)
    if tool_name == "get_researcher":
        return get_researcher(store, **tool_args)

    return {"error": f"Unknown tool: {tool_name}"}

