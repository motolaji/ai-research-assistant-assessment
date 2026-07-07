TOOL_SCHEMAS = [
    {
        "name": "discover_projects",
        "description": "List research projects, optionally filtered by status or a keyword matching the title or organisation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by project status, e.g. Active, Completed"},
                "keyword": {"type": "string", "description": "Keyword to search in title or organisation"},
            },
            "required": [],
        },
    },
    {
    "name": "get_project",
    "description": "Retrieve full details of a specific research project by its project ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string", "description": "The project ID, e.g. PRJ001"},
        },
        "required": ["project_id"],
    },
},
{
    "name": "search_datasets",
    "description": "Search available datasets by keyword (matches name or description), and optionally filter by restricted status or minimum record count.",
    "input_schema": {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "Keyword to search in dataset name or description, e.g. diabetes, cardiology"},
            "restricted": {"type": "boolean", "description": "Filter to only restricted (true) or only unrestricted (false) datasets"},
            "min_records": {"type": "integer", "description": "Only return datasets with more than this number of records"},
        },
        "required": [],
    },
},
{
    "name": "get_dataset_metadata",
    "description": "Retrieve full metadata for a specific dataset by its dataset ID, including its fields and record count.",
    "input_schema": {
        "type": "object",
        "properties": {
            "dataset_id": {"type": "string", "description": "The dataset ID, e.g. DS001"},
        },
        "required": ["dataset_id"],
    },
},
{
    "name": "execute_query",
    "description": "Run an analytical query against a specific dataset and return the results, subject to governance rules such as small cell suppression and access control.",
    "input_schema": {
        "type": "object",
        "properties": {
            "dataset_id": {"type": "string", "description": "The dataset ID to query, e.g. DS001"},
        },
        "required": ["dataset_id"],
    },
},
{
    "name": "get_researcher",
    "description": "Look up a researcher by username, or search researchers by role (e.g. Researcher, Administrator).",
    "input_schema": {
        "type": "object",
        "properties": {
            "username": {"type": "string", "description": "The researcher's username, e.g. alice"},
            "role": {"type": "string", "description": "Filter by role, e.g. Researcher, Administrator"},
        },
        "required": [],
    },
},
]