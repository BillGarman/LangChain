from transformers import load_tool
from langchain.experimental.autonomous_agents.hugginggpt.task_planner import load_chat_planner
from langchain.experimental.autonomous_agents.hugginggpt.task_executor import TaskExecutor
from langchain.experimental.autonomous_agents.hugginggpt.repsonse_generator import load_response_generator

class HuggingGPT:
    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = tools
        self.chat_planner = load_chat_planner(llm)
        self.response_generator = load_response_generator(llm)
        self.task_executor = None
    
    def run(self, input):
        plan = self.chat_planner.plan(inputs={"input": input, "hf_tools": self.tools})
        self.task_executor = TaskExecutor(plan)
        self.task_executor.run()
        response = self.response_generator.generate({"task_execution": self.task_executor})
        return response