import asyncio
import os
import requests
from typing import Any
from pydantic import BaseModel, Field

# --- Framework Imports ---
from beeai_framework.agents.requirement import RequirementAgent
from beeai_framework.agents.requirement.requirements.conditional import ConditionalRequirement
from beeai_framework.backend import ChatModel
from beeai_framework.context import RunContext
from beeai_framework.emitter import Emitter
from beeai_framework.tools import Tool, ToolRunOptions, StringToolOutput
from beeai_framework.tools.think import ThinkTool

# --- 1. Define the Input Schema ---
class SocialSearchInput(BaseModel):
    role_type: str = Field(description="The target: 'Hiring Manager' or 'Founder'")
    industry: str = Field(description="The sector, e.g., 'Android Developer', 'Fintech'")
    location: str = Field(description="Target city or country")

# --- 2. Define the Custom SerpAPI Tool ---
class SerpApiSocialTool(Tool[SocialSearchInput, ToolRunOptions, StringToolOutput]):
    name = "SerpApiSocialSearch"
    description = "Searches professional LinkedIn profiles via Google to find decision-makers."
    
    @property
    def input_schema(self) -> type[SocialSearchInput]:
        return SocialSearchInput

    def __init__(self, api_key: str, options: dict[str, Any] | None = None) -> None:
        super().__init__(options)
        self.api_key = api_key
        self.search_count = 0  

    def _create_emitter(self) -> Emitter:
        return Emitter.root().child(namespace=["tool", "social", "search"], creator=self)

    async def _run(self, input: SocialSearchInput, options: ToolRunOptions | None, context: RunContext) -> StringToolOutput:
        if self.search_count >= 2:
            return StringToolOutput(result="Search blocked: Session limit reached.")

        self.search_count += 1
        search_query = f'site:linkedin.com/in "{input.role_type}" "{input.industry}" "{input.location}"'
        if input.role_type == "Hiring Manager":
            search_query += ' "hiring"'

        print(f"\n[SerpAPI] Executing search {self.search_count}/2...")

        url = "https://serpapi.com/search"
        params = {"engine": "google", "q": search_query, "api_key": self.api_key, "no_cache": "false"}

        try:
            response = await asyncio.to_thread(requests.get, url, params=params)
            data = response.json()
            results = data.get("organic_results", [])
            formatted = [f"Title: {res.get('title')}\nLink: {res.get('link')}\n" for res in results[:3]]
            return StringToolOutput(result="\n".join(formatted) if formatted else "No profiles found.")
        except Exception as e:
            return StringToolOutput(result=f"API Error: {str(e)}")

# --- 3. Main Execution ---
async def main() -> None:
    SERP_API_KEY = "YOUR_SERP_API_KEY"

    social_tool = SerpApiSocialTool(api_key=SERP_API_KEY)
    lead_agent = RequirementAgent(
        name="SocialLeadSpecialist",
        llm=ChatModel.from_name("ollama:granite3.3:8b"),
        tools=[ThinkTool(), social_tool],
        requirements=[ConditionalRequirement(ThinkTool, force_at_step=1)],
        role="Lead Generation Specialist",
        instructions="Find LinkedIn profiles for specific professions. Provide a clean list of names and links."
    )

    query = "Find 2 Hiring Managers for Android Development in San Francisco, California."
    try:
        response = await lead_agent.run(query)
        print("\n--- Agent Response ---\n", response.last_message.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())