import re
import time
import json
from sys_prompt import SYSTEM_PROMPT
from data_store import DataStore
from governance import GovernanceContext, PolicyChain
from tool_schemas import TOOL_SCHEMAS, dispatch_tool


ID_PATTERN = re.compile(r"\b(PRJ\d+|DS\d+)\b")

def extract_sources(result: dict, sources: list[str]) -> None:
    text_blob = json.dumps(result)
    for match in ID_PATTERN.findall(text_blob):
        if match not in sources:
            sources.append(match)
            

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
                system=SYSTEM_PROMPT,
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

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})

        return "I was unable to complete this request within the allowed number of steps.", sources


