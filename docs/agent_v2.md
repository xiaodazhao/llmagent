# TBM Agent V2 Architecture

`/api/tbm/agent_v2` is the supervisor-style multi-agent entry point for the TBM
analysis backend. It keeps the existing data analysis pipeline, but changes the
question handling layer from one rule-based agent into a supervisor plus several
specialist domain agents.

## Current Shape

```text
User question
  -> FastAPI route: backend/routes/tbm.py
  -> TBMSupervisorAgent
  -> supervisor_plan
  -> DomainAgent
  -> TBMTools
  -> analyze_tbm_data and related services
  -> answer + highlights + tool_results
```

The old endpoint is still available:

```text
POST /api/tbm/agent
```

The new supervisor endpoint is:

```text
POST /api/tbm/agent_v2
GET  /api/tbm/agent_v2/capabilities
```

## Agent Roles

| Agent | Responsibility | Main tools |
| --- | --- | --- |
| `DataAgent` | Available dates, CSV loading, compact daily analysis | `list_dates`, `load_day`, `analyze_day` |
| `OperationAgent` | Work, stop, transition, abnormal states, efficiency | `analyze_operation` |
| `SafetyAgent` | Gas statistics and exceedance events | `analyze_gas` |
| `GeologyAgent` | Geology fusion, coupling, forward risk, risk/speed profiles | `analyze_geology`, `analyze_forward_risk`, `risk_profile` |
| `TwinAgent` | Compact digital-twin state snapshot | `get_digital_twin_state` |
| `MemoryAgent` | Comparison with saved historical memory records | `compare_history` |

## Runtime Flow

1. `backend/routes/tbm.py` receives an `AgentRequest`.
2. `TBMSupervisorAgent.run()` reads:
   - `query`
   - `date`
   - `use_llm`
   - `verbose`
3. The supervisor builds a `supervisor_plan` from query keywords.
4. Each planned domain agent calls one or more tools in `TBMTools`.
5. `TBMTools` loads the real TBM CSV data and reuses the existing analysis
   services.
6. The supervisor returns a compact response by default.
7. If `verbose=true`, the response also includes full nested tool outputs.

## Response Contract

Compact response:

```json
{
  "success": true,
  "data": {
    "mode": "supervisor_v2",
    "verbose": false,
    "supervisor_plan": [],
    "routed_agents": [],
    "answer": "...",
    "highlights": {},
    "agent_results": [],
    "tool_results": []
  },
  "message": "TBM supervisor completed."
}
```

Use `answer` and `highlights` for the main frontend display. Keep
`tool_results` for expandable technical details.

## Example Requests

List available dates:

```json
{
  "query": "有哪些可用日期",
  "date": null,
  "use_llm": false,
  "verbose": false
}
```

Expected routing:

```text
DataAgent(list_dates)
```

Analyze gas, geology risk, and digital twin state:

```json
{
  "query": "分析瓦斯、地质风险和数字孪生状态",
  "date": "2023-12-30",
  "use_llm": false,
  "verbose": false
}
```

Expected routing:

```text
SafetyAgent(analyze_gas)
GeologyAgent(analyze_geology)
TwinAgent(get_digital_twin_state)
```

## Smoke Test

Start the backend first:

```powershell
cd backend
uvicorn app:app --reload --port 8000
```

Then run the smoke test from the repository root:

```powershell
python backend/scripts/test_agent_v2.py
```

The script uses your real TBM data through the HTTP API. It checks:

- supervisor capabilities
- available-date routing
- multi-agent routing
- compact response mode
- verbose response mode
- clean failure for an invalid date

To test a specific date:

```powershell
python backend/scripts/test_agent_v2.py --date 2023-12-30
```

## Notes

This is a supervisor-style architecture, not a full LangGraph migration. It is
intentionally lightweight: it avoids adding a new framework dependency while
still making the agent roles, routing plan, and tool calls explicit.
