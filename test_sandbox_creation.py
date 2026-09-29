from google.adk.code_executors import AgentEngineSandboxCodeExecutor

REASONING_ENGINE_ID = "projects/698694960991/locations/us-east1/reasoningEngines/2926440357279301632"

print(f"Initializing AgentEngineSandboxCodeExecutor with agent_engine_resource_name={REASONING_ENGINE_ID}...")
executor = AgentEngineSandboxCodeExecutor(agent_engine_resource_name=REASONING_ENGINE_ID)
print(f"Executor initialized:")
print(f"  sandbox_resource_name: {getattr(executor, 'sandbox_resource_name', None)}")
print(f"  agent_engine_resource_name: {getattr(executor, 'agent_engine_resource_name', None)}")

# Test a code execution through executor
import asyncio
async def test_run():
    print("Testing code execution...")
    res = await executor.execute_code(None, "print('Hello from K8s Sandbox!')")
    print(f"Execution result: {res}")

asyncio.run(test_run())
