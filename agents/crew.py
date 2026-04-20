"""
Multi-Agent Crew: Orchestrate financial analysis agents

Architecture:
  User Query
      ↓
  🧠 Planner Agent (Orchestrator)
      ↓ (decides which agents + inputs)
  ┌─────────────┬──────────────┬─────────────────┐
  ↓             ↓              ↓
📥 Retriever  📊 Analyst   📈 Visualizer
(Neo4j→      (Growth,      (Charts)
 ChromaDB→    Margins,
 DuckDB)      Trends)
  │             │              │
  └─────────────┴──────────────┘
         ↓
  🧾 Reporter Agent
      ↓
  Final Report
"""

from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool as CrewBaseTool
import os
from typing import Any

from config import AGENT_CONFIG, TASK_TEMPLATES, LLM_CONFIG, GROQ_API_KEY
from tools.neo4j_tool import create_neo4j_tool
from tools.retriever_tool import create_retriever_tool
from tools.analyst_tool import create_analyst_tool
from tools.visualizer_tool import create_visualizer_tool


def wrap_langchain_tool(lc_tool) -> CrewBaseTool:
    """Wrap a langchain Tool as a CrewAI BaseTool."""
    tool_desc = lc_tool.description + " Pass all parameters as a single query string, e.g. 'company=AMD year=2021 What is revenue?'"

    class WrappedTool(CrewBaseTool):
        name: str = lc_tool.name
        description: str = tool_desc
        _lc_tool: Any = None

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._lc_tool = lc_tool

        def _run(self, query: str) -> str:
            return self._lc_tool.run(query)

    return WrappedTool()


class FinancialAnalysisCrew:
    """Multi-agent crew for financial analysis."""
    
    def __init__(self):
        """Initialize the crew with agents and tools."""
        # Initialize LLM with retry logic for rate limits
        os.environ["GROQ_API_KEY"] = GROQ_API_KEY or ""
        os.environ["LITELLM_NUM_RETRIES"] = "3"
        os.environ["LITELLM_RETRY_WAIT_TIME"] = "15"
        self.llm = LLM_CONFIG['model']
        
        # Initialize tools (wrap langchain tools for CrewAI compatibility)
        self.neo4j_tool = wrap_langchain_tool(create_neo4j_tool())
        self.retriever_tool = wrap_langchain_tool(create_retriever_tool())
        self.analyst_tool = wrap_langchain_tool(create_analyst_tool())
        self.visualizer_tool = wrap_langchain_tool(create_visualizer_tool())
        
        # Create agents
        self.planner_agent = self._create_planner_agent()
        self.retriever_agent = self._create_retriever_agent()
        self.analyst_agent = self._create_analyst_agent()
        self.visualizer_agent = self._create_visualizer_agent()
        self.reporter_agent = self._create_reporter_agent()
    
    def _create_planner_agent(self) -> Agent:
        """Create the planner agent (orchestrator)."""
        config = AGENT_CONFIG['planner']
        
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            verbose=config['verbose'],
            allow_delegation=config['allow_delegation'],
            llm=self.llm,
        )
    
    def _create_retriever_agent(self) -> Agent:
        """Create the retriever agent with Neo4j + retriever tools."""
        config = AGENT_CONFIG['retriever']
        
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'] + "\n\nIMPORTANT: When you have gathered enough data, provide your Final Answer as plain text, NOT as a tool call.",
            verbose=config['verbose'],
            allow_delegation=config['allow_delegation'],
            tools=[self.neo4j_tool, self.retriever_tool],
            llm=self.llm,
            max_iter=6,
        )
    
    def _create_analyst_agent(self) -> Agent:
        """Create the analyst agent."""
        config = AGENT_CONFIG['analyst']
        
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            verbose=config['verbose'],
            allow_delegation=config['allow_delegation'],
            tools=[],  # No tools - analyst works from context data passed by retriever
            llm=self.llm,
        )
    
    def _create_visualizer_agent(self) -> Agent:
        """Create the visualizer agent."""
        config = AGENT_CONFIG['visualizer']
        
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            verbose=config['verbose'],
            allow_delegation=config['allow_delegation'],
            tools=[],  # No tools - describe chart configs in text, avoid Groq tool_use conflicts
            llm=self.llm,
        )
    
    def _create_reporter_agent(self) -> Agent:
        """Create the reporter agent."""
        config = AGENT_CONFIG['reporter']
        
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            verbose=config['verbose'],
            allow_delegation=config['allow_delegation'],
            llm=self.llm,
        )
    
    def analyze_query(self, query: str) -> str:
        """
        Analyze a user query using the multi-agent crew.
        
        Args:
            query: User query
            
        Returns:
            Final analysis report
        """
        # Task 1: Planning
        planning_task = Task(
            description=TASK_TEMPLATES['planning'].format(query=query),
            agent=self.planner_agent,
            expected_output="A detailed execution plan with steps for each agent",
        )
        
        # Task 2: Data Retrieval (receives planner context)
        retrieval_task = Task(
            description=TASK_TEMPLATES['retrieval'].format(
                query=query,
                filters="{}"
            ),
            agent=self.retriever_agent,
            expected_output="Relevant financial data with citations from Neo4j, ChromaDB, and DuckDB",
            context=[planning_task],
        )
        
        # Task 3: Analysis (receives retrieval output)
        analysis_task = Task(
            description=TASK_TEMPLATES['analysis'].format(
                data="Use the retrieved data from the previous task",
                query=query
            ),
            agent=self.analyst_agent,
            expected_output="Financial analysis with calculations, trends, and insights",
            context=[retrieval_task],
        )
        
        # Task 4: Visualization (receives retrieval + analysis)
        visualization_task = Task(
            description=TASK_TEMPLATES['visualization'].format(
                data="Use the retrieved data from previous tasks",
                analysis="Use the analysis from previous task",
                query=query
            ),
            agent=self.visualizer_agent,
            expected_output="Path to saved visualization chart",
            context=[retrieval_task, analysis_task],
        )
        
        # Task 5: Reporting (receives all previous outputs)
        reporting_task = Task(
            description=TASK_TEMPLATES['reporting'].format(
                query=query,
                data="Use the retrieved data from previous tasks",
                analysis="Use the analysis from previous tasks",
                visualizations="Use the visualizations from previous task"
            ),
            agent=self.reporter_agent,
            expected_output="Comprehensive financial report with executive summary and key findings",
            context=[retrieval_task, analysis_task, visualization_task],
        )
        
        # Create crew
        crew = Crew(
            agents=[
                self.planner_agent,
                self.retriever_agent,
                self.analyst_agent,
                self.visualizer_agent,
                self.reporter_agent,
            ],
            tasks=[
                planning_task,
                retrieval_task,
                analysis_task,
                visualization_task,
                reporting_task,
            ],
            process=Process.sequential,  # Execute tasks in order
            verbose=True,
        )
        
        # Execute
        result = crew.kickoff()
        
        return result


def main():
    """Test the multi-agent crew."""
    print("\n" + "="*80)
    print("MULTI-AGENT FINANCIAL ANALYSIS CREW")
    print("="*80)
    
    # Initialize crew
    crew = FinancialAnalysisCrew()
    
    # Single test query
    query = "What is AMD's revenue in 2021?"
    print(f"\n{'─'*80}")
    print(f"Query: {query}")
    print(f"{'─'*80}\n")

    try:
        result = crew.analyze_query(query)
        print(f"\n✅ Result:\n{result}")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
