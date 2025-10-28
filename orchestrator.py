import os
import json
from openai import OpenAI
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import re

def safe_json_parse(response_text: str) -> dict:
    """
    Attempts to safely parse JSON from LLM response text.
    Fixes common issues: trailing commas, unescaped quotes, extra text.
    """
    try:
        # Extract JSON substring (ignore anything before/after)
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            raise ValueError("No JSON object found in response.")
        
        json_str = json_match.group(0)

        # Clean up common LLM formatting errors
        json_str = json_str.replace("\n", " ").replace("\r", " ")
        json_str = re.sub(r',\s*}', '}', json_str)   # remove trailing commas
        json_str = re.sub(r',\s*]', ']', json_str)

        data = json.loads(json_str)
        return data
    
    except Exception as e:
        print(f"⚠️ JSON parse error: {e}")
        return {}

class AgentType(Enum):
    RESEARCH = "research"
    VALIDATOR = "validator"
    SYNTHESIS = "synthesis"

class Priority(Enum):
    CRITICAL = "critical"  # Must verify - deal breakers
    HIGH = "high"          # Important for decision
    MEDIUM = "medium"      # Nice to have
    LOW = "low"            # Background info

@dataclass
class ResearchTask:
    """Single research task for an agent"""
    task_id: str
    agent_type: AgentType
    priority: Priority
    query: str
    context: str
    reasoning: str  # Why this task matters
    
    def to_dict(self):
        return {
            'task_id': self.task_id,
            'agent': self.agent_type.value,
            'priority': self.priority.value,
            'query': self.query,
            'context': self.context,
            'reasoning': self.reasoning
        }

@dataclass
class ResearchPlan:
    """Complete research plan with prioritized tasks"""
    company_name: str
    deck_summary: str
    critical_gaps: List[str]
    tasks: List[ResearchTask]
    estimated_cost_usd: float
    
    def to_dict(self):
        return {
            'company_name': self.company_name,
            'deck_summary': self.deck_summary,
            'critical_gaps': self.critical_gaps,
            'tasks': [task.to_dict() for task in self.tasks],
            'estimated_cost': f"${self.estimated_cost_usd:.3f}"
        }


class OrchestratorAgent:
    """
    The Orchestrator Agent - Master planner and coordinator
    
    Responsibilities:
    1. Analyze pitch deck to extract core info
    2. Identify what's missing or suspicious
    3. Generate prioritized research tasks
    4. Coordinate execution (future: delegate to other agents)
    """
    
    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-haiku"):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.model = model
        self.total_cost = 0.0
        
    def analyze_deck(self, deck_text: str) -> Dict:
        """
        Step 1: Extract core information from pitch deck
        Returns: Structured data about the company
        """
        print("\n🧠 ORCHESTRATOR: Analyzing pitch deck...")
        
        prompt = f"""You are an AI investment analyst. Analyze this pitch deck and extract key information.

    PITCH DECK:
    {deck_text[:6000]}

    Return ONLY valid JSON (no comments, no trailing commas). Use this exact schema:


    "company_name": "",
    "tagline": "",
    "founders": [],
    "stage": "",
    "funding_ask": null,
    "problem": "",
    "solution": "",
    "traction": null,
    "claims": [],
    "team_info": "",
    "competitors_mentioned": [],
    "website": null

    Focus on extracting SPECIFIC CLAIMS that can be verified (user counts, revenue, growth rates, partnerships).
    Return ONLY valid JSON.
    """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            deck_analysis = json.loads(content)
            
            # Estimate cost (rough: $0.003 per 1k tokens for Haiku)
            tokens_used = len(prompt) // 4 + 1000  # Rough estimate
            self.total_cost += (tokens_used / 1000) * 0.003
            
            print(f"✅ Extracted info for: {deck_analysis.get('company_name', 'Unknown')}")
            return deck_analysis
            
        except Exception as e:
            print(f"❌ Error analyzing deck: {e}")
            return None
    
    def identify_gaps(self, deck_analysis: Dict) -> List[str]:
        """
        Step 2: Identify critical information gaps
        Uses reasoning to determine what's missing or suspicious
        """
        print("\n🔍 ORCHESTRATOR: Identifying information gaps...")
        
        prompt = """You are analyzing a startup pitch deck for an investment manager.

EXTRACTED INFO:
{json.dumps(deck_analysis, indent=2)}

Identify CRITICAL information gaps and red flags. Consider:

RED FLAGS (highest priority to investigate):
- Claims without evidence (e.g., "10k users" but no proof)
- Missing team backgrounds (founders with no LinkedIn/history)
- No competitors mentioned (unrealistic)
- Vague metrics ("growing fast" without numbers)
- Funding ask without use of funds

INFORMATION GAPS (important to fill):
- Market size not mentioned
- No financial projections
- Technology/product not explained
- No customer testimonials or case studies

Return a JSON array of gaps, PRIORITIZED by importance for investment decision:
[
  "CRITICAL: Claims 10k users but no traction metrics provided",
  "CRITICAL: Founders not identified - need to verify team exists",
  "HIGH: No competitors mentioned - need to research market landscape",
  "MEDIUM: Financial projections missing"
]

Return 5-8 gaps max. Focus on what would make or break an investment decision.
Return ONLY a valid JSON array."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800
            )
            
            content = response.choices[0].message.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            gaps = json.loads(content)
            
            tokens_used = len(prompt) // 4 + 800
            self.total_cost += (tokens_used / 1000) * 0.003
            
            print(f"✅ Identified {len(gaps)} critical gaps")
            for i, gap in enumerate(gaps[:3], 1):
                print(f"   {i}. {gap[:80]}...")
            
            return gaps
            
        except Exception as e:
            print(f"❌ Error identifying gaps: {e}")
            return []
    
    def create_research_plan(self, deck_analysis: Dict, gaps: List[str]) -> ResearchPlan:
        """
        Step 3: Create prioritized research plan with specific tasks
        This is where the orchestrator shows its intelligence
        """
        print("\n📋 ORCHESTRATOR: Creating research plan...")
        
        company_name = deck_analysis.get('company_name', 'Unknown')
        founders = deck_analysis.get('founders', [])
        claims = deck_analysis.get('claims', [])
        competitors = deck_analysis.get('competitors_mentioned', [])
        
        tasks = []
        task_counter = 0
        
        # CRITICAL TASKS - Must verify these
        
        # Task 1: Verify company exists and is legitimate
        if deck_analysis.get('website'):
            task_counter += 1
            tasks.append(ResearchTask(
                task_id=f"T{task_counter:03d}",
                agent_type=AgentType.RESEARCH,
                priority=Priority.CRITICAL,
                query=f"Verify {company_name} website and company legitimacy",
                context=f"Website: {deck_analysis.get('website')}",
                reasoning="Must confirm company actually exists before further research"
            ))
        
        # Task 2: Verify founders exist and check backgrounds
        if founders:
            for founder in founders[:3]:  # Limit to 3 founders to save costs
                task_counter += 1
                tasks.append(ResearchTask(
                    task_id=f"T{task_counter:03d}",
                    agent_type=AgentType.RESEARCH,
                    priority=Priority.CRITICAL,
                    query=f"Find LinkedIn profile and background for {founder}",
                    context=f"Founder of {company_name}",
                    reasoning="Verify founder exists and has relevant experience"
                ))
        
        # Task 3: Validate key claims
        for claim in claims[:2]:  # Top 2 claims
            task_counter += 1
            tasks.append(ResearchTask(
                task_id=f"T{task_counter:03d}",
                agent_type=AgentType.VALIDATOR,
                priority=Priority.CRITICAL,
                query=f"Verify claim: {claim}",
                context=f"Company: {company_name}",
                reasoning="Need to validate specific claims made in pitch deck"
            ))
        
        # HIGH PRIORITY TASKS
        
        # Task 4: Research competitive landscape
        task_counter += 1
        tasks.append(ResearchTask(
            task_id=f"T{task_counter:03d}",
            agent_type=AgentType.RESEARCH,
            priority=Priority.HIGH,
            query=f"Find competitors and alternatives to {company_name}",
            context=f"Industry: {deck_analysis.get('problem', 'Not specified')}",
            reasoning="Understand market positioning and competitive threats"
        ))
        
        # Task 5: Check funding history
        task_counter += 1
        tasks.append(ResearchTask(
            task_id=f"T{task_counter:03d}",
            agent_type=AgentType.RESEARCH,
            priority=Priority.HIGH,
            query=f"Find funding history for {company_name} on Crunchbase",
            context=f"Current stage: {deck_analysis.get('stage', 'Unknown')}",
            reasoning="Verify funding stage and previous investors"
        ))
        
        # Task 6: Recent news and developments
        task_counter += 1
        tasks.append(ResearchTask(
            task_id=f"T{task_counter:03d}",
            agent_type=AgentType.RESEARCH,
            priority=Priority.MEDIUM,
            query=f"Find recent news about {company_name} from 2024-2025",
            context=f"Focus on product launches, partnerships, pivots",
            reasoning="Identify recent developments not in deck"
        ))
        
        # Estimate total cost (rough)
        estimated_cost = self.total_cost + (len(tasks) * 0.05)  # ~$0.05 per task
        
        plan = ResearchPlan(
            company_name=company_name,
            deck_summary=f"{deck_analysis.get('tagline', 'No tagline')} | Stage: {deck_analysis.get('stage', 'Unknown')}",
            critical_gaps=gaps,
            tasks=tasks,
            estimated_cost_usd=estimated_cost
        )
        
        print(f"✅ Created plan with {len(tasks)} tasks")
        print(f"   💰 Estimated cost: ${estimated_cost:.3f}")
        
        return plan
    
    def orchestrate(self, deck_text: str) -> Optional[ResearchPlan]:
        """
        Main orchestration flow
        Step 1: Analyze deck
        Step 2: Identify gaps
        Step 3: Create research plan
        """
        print("\n" + "="*60)
        print("🎯 ORCHESTRATOR AGENT - Starting Analysis")
        print("="*60)
        
        # Step 1: Analyze deck
        deck_analysis = self.analyze_deck(deck_text)
        if not deck_analysis:
            return None
        
        # Step 2: Identify gaps
        gaps = self.identify_gaps(deck_analysis)
        
        # Step 3: Create research plan
        plan = self.create_research_plan(deck_analysis, gaps)
        
        print("\n" + "="*60)
        print("✅ ORCHESTRATOR: Research plan ready")
        print(f"💰 Total LLM cost so far: ${self.total_cost:.4f}")
        print("="*60)
        
        return plan


# Simple test function
def test_orchestrator():
    """Test the orchestrator with sample deck text"""
    
    # Sample pitch deck text (simulating extracted text)
    sample_deck = """
    FoodFleet - The Uber for Food Trucks
    
    Founders: Sarah Chen (CEO), Mike Rodriguez (CTO)
    
    Problem: Food trucks struggle to find high-traffic locations and customers can't discover them easily.
    
    Solution: Our AI-powered platform connects food trucks with optimal locations and hungry customers in real-time.
    
    Traction: 
    - 10,000+ active users
    - 150 food trucks on platform
    - Growing 20% month-over-month
    
    Market: $2.5B food truck industry, growing 12% annually
    
    Funding: Raising $1.5M seed round
    
    Website: www.foodfleet.io
    """
    
    # Initialize orchestrator
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY not set")
        return
    
    orchestrator = OrchestratorAgent(api_key)
    
    # Run orchestration
    plan = orchestrator.orchestrate(sample_deck)
    
    if plan:
        print("\n" + "="*60)
        print("📊 FINAL RESEARCH PLAN")
        print("="*60)
        print(json.dumps(plan.to_dict(), indent=2))
        
        # Print task summary
        print("\n📋 TASK BREAKDOWN:")
        critical = [t for t in plan.tasks if t.priority == Priority.CRITICAL]
        high = [t for t in plan.tasks if t.priority == Priority.HIGH]
        medium = [t for t in plan.tasks if t.priority == Priority.MEDIUM]
        
        print(f"   🔴 CRITICAL: {len(critical)} tasks")
        print(f"   🟡 HIGH: {len(high)} tasks")
        print(f"   🟢 MEDIUM: {len(medium)} tasks")
        
        print("\n🎯 Next step: Execute these tasks with Research & Validator agents")


if __name__ == "__main__":
    test_orchestrator()