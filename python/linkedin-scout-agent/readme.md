<img width="1536" height="1024" alt="ChatGPT Image Feb 3, 2026, 01_48_24 PM" src="https://github.com/user-attachments/assets/6aad8944-20df-484c-89ad-4088b7f93512" />


# LinkedIn Scout Agent 🤖🔍  
**Building a Custom Agent with BeeAI Framework**
This project introduces the LinkedIn Scout Agent, an intelligent agent built using the BeeAI Framework to discover real hiring managers, founders, and decision-makers on LinkedIn. Instead of relying on manual searches or unreliable scraping, the agent interprets natural language queries, reasons through intent, and identifies the most relevant profiles based on role, industry, and location.

Under the hood, the agent follows a structured, reasoning-first workflow. It plans its actions using ThinkTool, executes controlled Google searches via a custom SerpAPI tool, and returns clean, predictable results using strict input schemas. By enforcing limits, observability, and step-by-step reasoning, the agent operates safely and reliably, making it suitable for real-world, production-grade use cases. Read more on our [Newsletter Website](https://www.snackonai.com/)

---
## 🧠 Technology Stack

### Ollama
A lightweight runtime that allows you to run large language models locally using simple terminal commands.

### IBM Granite 3.3 (8B)
A native open-source large language model optimized for:
- Reasoning
- Tool usage
- Enterprise-grade reliability

### Python 3.10+
Required runtime version for compatibility and modern async workflows.

### SerpAPI (Custom Tool Integration)
Used to perform advanced Google searches (Google Dorking) to discover LinkedIn profiles and real decision-makers.

### ThinkTool
Forces the agent to pause, reason, and plan before responding — ensuring step-by-step thinking instead of rushed or random answers.

---

## 🧩 Architecture

The agent follows a structured execution flow:
1. Understand the user intent
2. Think and plan using `ThinkTool`
3. Decide whether external data is required
4. Execute a controlled search via SerpAPI
5. Return clean, structured results

<img width="594" height="787" alt="image" src="https://github.com/user-attachments/assets/29e6c386-3afd-4280-af6f-5eac21dcb179" />

This architecture ensures predictability, safety, and explainability.

---

## ⚙️ Setup and Implementation

### 1️⃣ Download the LLM Model

```bash
ollama pull granite3.3:8b

```
### 2️⃣ Create Project Directory
```bash

mkdir beeai_custom_agent
cd beeai_custom_agent

```
### 3️⃣ Create and Activate Virtual Environment
```bash

python -m venv venv

```
- Activate it:

- Windows
```bash 

venv\Scripts\activate

```
Mac/Linux
```bash

source venv/bin/activate

```
### 4️⃣ Install Dependencies
```bash

pip install beeai-framework requests
pip install pydantic

```
###🧠 Agent Implementation
```bash 

linkedin-scout-agent.py
 
```

### ▶️ Running the Agent
- Update the following line with your SerpAPI key:
```bash

SERP_API_KEY = "YOUR_SERP_API_KEY"

```
Run the agent:
```bash

python linkedin_scout_agent.py

```
🧪 Example Query
```bash

query = "Find 2 Hiring Managers for Android Development in San Francisco, California."

```
### Output
```bash

--- Agent Response ---

1. Name: Sarah Lee  
   LinkedIn: https://www.linkedin.com/in/sarahleeandroid/  
   Position: Senior Android Developer & Hiring Manager  
   Location: San Francisco, California

2. Name: John Smith  
   LinkedIn: https://www.linkedin.com/in/john-smith-android/  
   Position: Android Development Lead & Hiring Manager  
   Location: San Francisco, California

