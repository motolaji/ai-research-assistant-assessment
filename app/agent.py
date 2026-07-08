import time
import json
from app.sys_prompt import SYSTEM_PROMPT
from app.data_store import DataStore
from app.governance import PolicyChain
from app.tool_schemas import TOOL_SCHEMAS
from app.mcp_server import dispatch_tool



def extract_sources(result: dict, sources: list[str]) -> None:
    if "username" in result and "role" in result:
        if result["username"] not in sources:
            sources.append(result["username"])
        return

    if "id" in result:
        if result["id"] not in sources:
            sources.append(result["id"])
        return

    items = []
    if "project" in result:
        items = [result["project"]]
    elif "projects" in result:
        items = result["projects"]
    elif "dataset" in result:
        items = [result["dataset"]]
    elif "datasets" in result:
        items = result["datasets"]
    elif "researcher" in result:
        items = [result["researcher"]]
    elif "researchers" in result:
        items = result["researchers"]

    for item in items:
        if isinstance(item, str):
            continue
        entity_id = item.get("id") or item.get("username")
        if entity_id and entity_id not in sources:
            sources.append(entity_id)

    dataset_id = result.get("dataset_id")
    if dataset_id and dataset_id not in sources:
        sources.append(dataset_id)
            

class LLMProvider:
    def call(self, messages: list, tools: list):
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def call(self, messages: list, tools: list):
        return self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )


class OpenAIProvider(LLMProvider):
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def call(self, messages: list, tools: list):
        return self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            temperature=0,
            tools=tools,
            messages=messages,
        )  



class ResearchAgent:
    def __init__(self, provider: LLMProvider, store: DataStore, chain: PolicyChain, max_iterations: int = 8):
        self.provider = provider
        self.store = store
        self.chain = chain
        self.max_iterations = max_iterations

    def run(self, question: str, researcher: dict | None, trace_id: str, audit_entry) -> tuple[str, list[str]]:
        messages = [{"role": "user", "content": question}]
        sources: list[str] = []

        for _ in range(self.max_iterations):
            response = self.provider.call(messages, TOOL_SCHEMAS)

            if response.stop_reason != "tool_use":
                final_text = "".join(
                    block.text for block in response.content if block.type == "text"
                )
                return final_text, sources

            # Claude wants to call one or more tools
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue
                #print(f"[DEBUG] tool={block.name} args={block.input}") # debugging

                start = time.perf_counter()

                start = time.perf_counter()
                result = dispatch_tool(
                    tool_name=block.name,
                    tool_args=block.input,
                    store=self.store,
                    chain=self.chain,
                    researcher=researcher,
                    trace_id=trace_id,
                )
                duration_ms = (time.perf_counter() - start) * 1000

                audit_entry.record_tool_call(
                    tool=block.name,
                    args=block.input,
                    duration_ms=duration_ms,
                    policies_fired=result.get("_policies_fired", []),
                )

                extract_sources(result, sources)

                #print(f"[DEBUG] result={result} sources_so_far={sources}") # debugging

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})

        return "I was unable to complete this request within the allowed number of steps.", sources


