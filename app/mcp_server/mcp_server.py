# from app.datastore import DataStore
# from app.governance import GovernanceContext, PolicyChain
# from app.tool_schemas import TOOL_SCHEMAS


# def discover_projects(store: DataStore, status: str | None = None, keyword: str | None = None) -> dict:
#     results = store.search_projects(status=status, keyword=keyword)
#     return {"projects": results, "count": len(results)}

# def get_project(store: DataStore, project_id: str) -> dict:
#     project = store.get_project_by_id(project_id)
#     if project is None:
#         return {"error": f"Project with ID '{project_id}' not found."}
#     return project

# def search_datasets_tool(store: DataStore, keyword: str | None = None, restricted: bool | None = None, min_records: int | None = None) -> dict:
#     results = store.search_datasets(keyword=keyword, restricted=restricted, min_records=min_records)
#     return {"datasets": results, "count": len(results)}

# def get_dataset_metadata(store: DataStore, dataset_id: str) -> dict:
#     dataset = store.get_dataset_by_id(dataset_id)
#     if dataset is None:
#         return {"error": f"Dataset with ID '{dataset_id}' not found."}
#     return dataset

# def get_researcher(store: DataStore, username: str | None = None, role: str | None = None) -> dict:
#     if username is not None:
#         researcher = store.get_researcher_by_username(username)
#         if researcher is None:
#             return {"error": f"Researcher with username '{username}' not found."}
#         return researcher
#     else:
#         results = store.search_researchers(role=role)
#         return {"researchers": results, "count": len(results)}
    
# def execute_query(store, chain, dataset_id, researcher, trace_id) -> dict:
#     dataset = store.get_dataset_by_id(dataset_id)
#     if dataset is None:
#         return {"error": "Dataset not found"}

#     raw_result = store.get_query_results(dataset_id)
#     if raw_result is None:
#         return {"error": "No query results available for this dataset"}

#     context = GovernanceContext(
#         tool_name="execute_query",
#         args={"dataset_id": dataset_id},
#         dataset=dataset,
#         researcher=researcher,
#         trace_id=trace_id,
#     )
#     governed_result = chain.apply(raw_result, context)
#     governed_result["_policies_fired"] = context.policies_fired
#     return governed_result   

# # dispatcher function for agent py

# def dispatch_tool(
#     tool_name: str,
#     tool_args: dict,
#     store: DataStore,
#     chain: PolicyChain,
#     researcher: dict | None,
#     trace_id: str,
# ) -> dict:
#     if tool_name == "discover_projects":
#         return discover_projects(store, **tool_args)
#     if tool_name == "get_project":
#         return get_project(store, **tool_args)
#     if tool_name == "search_datasets":
#         return search_datasets_tool(store, **tool_args)
#     if tool_name == "get_dataset_metadata":
#         return get_dataset_metadata(store, **tool_args)
#     if tool_name == "execute_query":
#         return execute_query(store, chain, researcher=researcher, trace_id=trace_id, **tool_args)
#     if tool_name == "get_researcher":
#         return get_researcher(store, **tool_args)

#     return {"error": f"Unknown tool: {tool_name}"}


from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from app.config import settings
from app.datastore import DataStore
from app.governance import GovernanceContext, PolicyChain, build_policy_chain


def discover_projects(
    store: DataStore,
    status: str | None = None,
    keyword: str | None = None,
) -> dict:
    results = store.search_projects(status=status, keyword=keyword)
    return {"projects": results, "count": len(results)}


def get_project(store: DataStore, project_id: str) -> dict:
    project = store.get_project_by_id(project_id)
    if project is None:
        return {"error": f"Project with ID '{project_id}' not found."}
    return project


def search_datasets_tool(
    store: DataStore,
    keyword: str | None = None,
    restricted: bool | None = None,
    min_records: int | None = None,
) -> dict:
    results = store.search_datasets(
        keyword=keyword,
        restricted=restricted,
        min_records=min_records,
    )
    return {"datasets": results, "count": len(results)}


def get_dataset_metadata(store: DataStore, dataset_id: str) -> dict:
    dataset = store.get_dataset_by_id(dataset_id)
    if dataset is None:
        return {"error": f"Dataset with ID '{dataset_id}' not found."}
    return dataset


def get_researcher(
    store: DataStore,
    username: str | None = None,
    role: str | None = None,
) -> dict:
    if username is not None:
        researcher = store.get_researcher_by_username(username)
        if researcher is None:
            return {"error": f"Researcher with username '{username}' not found."}
        return researcher

    results = store.search_researchers(role=role)
    return {"researchers": results, "count": len(results)}


def execute_query(
    store: DataStore,
    chain: PolicyChain,
    dataset_id: str,
    researcher: dict | None = None,
    trace_id: str | None = None,
) -> dict:
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
        trace_id=trace_id or str(uuid4()),
    )

    governed_result = chain.apply(raw_result, context)
    governed_result["_policies_fired"] = context.policies_fired
    return governed_result


def dispatch_tool(
    tool_name: str,
    tool_args: dict,
    store: DataStore,
    chain: PolicyChain,
    researcher: dict | None,
    trace_id: str,
) -> dict:
    """
    In-process dispatcher used by the REST assistant.

    The same tool implementations are also exposed below through the MCP server.
    This keeps one source of truth for tool behaviour and governance.
    """
    if tool_name == "discover_projects":
        return discover_projects(store, **tool_args)
    if tool_name == "get_project":
        return get_project(store, **tool_args)
    if tool_name == "search_datasets":
        return search_datasets_tool(store, **tool_args)
    if tool_name == "get_dataset_metadata":
        return get_dataset_metadata(store, **tool_args)
    if tool_name == "execute_query":
        return execute_query(
            store,
            chain,
            researcher=researcher,
            trace_id=trace_id,
            **tool_args,
        )
    if tool_name == "get_researcher":
        return get_researcher(store, **tool_args)

    return {"error": f"Unknown tool: {tool_name}"}



# Standalone MCP server


mcp = FastMCP("nhs-ai-research-assistant")

_mcp_store = DataStore(settings.data_dir)
_mcp_chain = build_policy_chain(_mcp_store)


@mcp.tool()
def discover_projects_tool(
    status: str | None = None,
    keyword: str | None = None,
) -> dict:
    """
    Discover available research projects.

    Optional filters:
    - status: filter projects by status
    - keyword: case-insensitive search over project title and organisation
    """
    return discover_projects(_mcp_store, status=status, keyword=keyword)


@mcp.tool()
def get_project_tool(project_id: str) -> dict:
    """
    Retrieve project information by project ID.
    """
    return get_project(_mcp_store, project_id=project_id)


@mcp.tool()
def search_datasets(
    keyword: str | None = None,
    restricted: bool | None = None,
    min_records: int | None = None,
) -> dict:
    """
    Search available datasets.

    Optional filters:
    - keyword: case-insensitive search over dataset name and description
    - restricted: filter by restricted/public datasets
    - min_records: return datasets above the supplied record threshold
    """
    return search_datasets_tool(
        _mcp_store,
        keyword=keyword,
        restricted=restricted,
        min_records=min_records,
    )


@mcp.tool()
def get_dataset_metadata_tool(dataset_id: str) -> dict:
    """
    Retrieve dataset metadata by dataset ID.
    """
    return get_dataset_metadata(_mcp_store, dataset_id=dataset_id)


@mcp.tool()
def execute_query_tool(
    dataset_id: str,
    researcher_username: str | None = None,
) -> dict:
    """
    Execute an approved analytical query against the supplied synthetic data.

    Results are passed through the governance policy chain before being returned.
    If researcher_username is supplied, identity-aware governance policies are applied.
    """
    researcher = None

    if researcher_username is not None:
        researcher = _mcp_store.get_researcher_by_username(researcher_username)
        if researcher is None:
            return {"error": f"Researcher with username '{researcher_username}' not found."}

    return execute_query(
        _mcp_store,
        _mcp_chain,
        dataset_id=dataset_id,
        researcher=researcher,
        trace_id=str(uuid4()),
    )


@mcp.tool()
def get_researcher_tool(
    username: str | None = None,
    role: str | None = None,
) -> dict:
    """
    Retrieve researcher information by username or role.
    """
    return get_researcher(_mcp_store, username=username, role=role)


if __name__ == "__main__":
    mcp.run()