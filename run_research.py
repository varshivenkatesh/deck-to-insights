"""
Research Runner - Executes research plan from orchestrator
Usage: python run_research.py <research_plan.json>
"""

import os
import sys
import json
from pathlib import Path
from research_agent import ResearchAgent

def main():
    print("="*70)
    print("🔬 RESEARCH AGENT - Executing Research Plan")
    print("="*70)
    
    # Check API key
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("\n❌ Error: OPENROUTER_API_KEY not set")
        sys.exit(1)
    
    # Check for research plan file
    if len(sys.argv) < 2:
        print("\n📖 Usage:")
        print("   python run_research.py <research_plan.json>")
        print("\nExample:")
        print("   python run_research.py deck_research_plan.json")
        sys.exit(1)
    
    plan_file = sys.argv[1]
    
    if not Path(plan_file).exists():
        print(f"\n❌ File not found: {plan_file}")
        sys.exit(1)
    
    # Load research plan
    print(f"\n📂 Loading research plan: {plan_file}")
    try:
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load plan: {e}")
        sys.exit(1)
    
    company_name = plan.get('company_name', 'Unknown')
    tasks = plan.get('tasks', [])
    
    if not tasks:
        print("❌ No tasks found in research plan")
        sys.exit(1)
    
    print(f"\n🏢 Company: {company_name}")
    print(f"📋 Total tasks: {len(tasks)}")
    
    # Filter for research tasks only (skip validator tasks for now)
    research_tasks = [t for t in tasks if t.get('agent') == 'research']
    
    print(f"🔬 Research tasks to execute: {len(research_tasks)}")
    
    # Ask for confirmation due to costs
    print(f"\n💰 Estimated cost: ${len(research_tasks) * 0.05:.2f}")
    print(f"⏱️  Estimated time: {len(research_tasks) * 30} seconds")
    
    confirm = input("\n⚠️  Proceed with research? (y/n): ")
    if confirm.lower() != 'y':
        print("❌ Cancelled by user")
        sys.exit(0)
    
    # Initialize research agent
    print("\n" + "="*70)
    print("🚀 Starting Research")
    print("="*70)
    
    agent = ResearchAgent(api_key)
    results = []
    
    # Execute each task
    for i, task in enumerate(research_tasks, 1):
        print(f"\n{'='*70}")
        print(f"📊 Task {i}/{len(research_tasks)}")
        print(f"{'='*70}")
        
        result = agent.execute_task(task)
        results.append(result.to_dict())
        
        # Show quick summary
        print(f"\n✅ Task {task['task_id']} complete:")
        print(f"   • Sources: {len(result.sources)}")
        print(f"   • Confidence: {result.confidence_score:.1%}")
        print(f"   • Findings: {len(result.key_findings)}")
        if result.red_flags:
            print(f"   • Red flags: {len(result.red_flags)}")
        
        print(f"\n💰 Cost so far: ${agent.total_cost:.4f}")
    
    # Cleanup
    agent.cleanup()
    
    # Save research results
    print("\n" + "="*70)
    print("💾 Saving Results")
    print("="*70)
    
    output_file = Path(plan_file).parent / f"{Path(plan_file).stem.replace('_research_plan', '')}_research_results.json"
    
    output_data = {
        'company_name': company_name,
        'research_completed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'tasks_executed': len(results),
        'total_cost': agent.total_cost,
        'results': results
    }
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Research results saved: {output_file}")
    except Exception as e:
        print(f"❌ Failed to save results: {e}")
    
    # Create validation plan
    print("\n" + "="*70)
    print("📋 Creating Validation Plan")
    print("="*70)
    
    # Convert dict results back to ResearchResult objects for validation plan
    from research_agent import ResearchResult
    result_objects = []
    for r in results:
        result_objects.append(ResearchResult(
            task_id=r['task_id'],
            query=r['query'],
            status=r['status'],
            sources=r['sources'],
            summary=r['summary'],
            key_findings=r['key_findings'],
            red_flags=r['red_flags'],
            confidence_score=r['confidence_score']
        ))
    
    # Load original deck analysis (need this for claims)
    deck_analysis_file = Path(plan_file).parent / f"{Path(plan_file).stem.replace('_research_plan', '')}_deck_analysis.json"
    
    if deck_analysis_file.exists():
        with open(deck_analysis_file, 'r', encoding='utf-8') as f:
            deck_analysis = json.load(f)
    else:
        # Extract from plan if available
        deck_analysis = {
            'company_name': company_name,
            'claims': [],
            'founders': []
        }
        print("⚠️  Original deck analysis not found, creating basic validation plan")
    
    validation_tasks = agent.create_validation_plan(result_objects, deck_analysis)
    
    # Save validation plan
    validation_file = Path(plan_file).parent / f"{Path(plan_file).stem.replace('_research_plan', '')}_validation_plan.json"
    
    validation_data = {
        'company_name': company_name,
        'validation_tasks': [task.to_dict() for task in validation_tasks],
        'total_tasks': len(validation_tasks)
    }
    
    try:
        with open(validation_file, 'w', encoding='utf-8') as f:
            json.dump(validation_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Validation plan saved: {validation_file}")
    except Exception as e:
        print(f"❌ Failed to save validation plan: {e}")
    
    # Final summary
    print("\n" + "="*70)
    print("✅ RESEARCH COMPLETE")
    print("="*70)
    print(f"\n🏢 Company: {company_name}")
    print(f"📊 Tasks executed: {len(results)}")
    print(f"💰 Total cost: ${agent.total_cost:.4f}")
    
    # Show key insights
    all_red_flags = []
    high_confidence_findings = []
    
    for result in result_objects:
        if result.red_flags:
            all_red_flags.extend(result.red_flags)
        if result.confidence_score > 0.7 and result.key_findings:
            high_confidence_findings.extend(result.key_findings[:2])
    
    if all_red_flags:
        print(f"\n🚨 Red Flags Found ({len(all_red_flags)}):")
        for flag in all_red_flags[:5]:
            print(f"   ⚠️  {flag}")
    
    if high_confidence_findings:
        print(f"\n✅ High-Confidence Findings ({len(high_confidence_findings)}):")
        for finding in high_confidence_findings[:5]:
            print(f"   • {finding}")
    
    print(f"\n📁 Output Files:")
    print(f"   • {output_file}")
    print(f"   • {validation_file}")
    
    print(f"\n🎯 Next Steps:")
    print(f"   1. ✅ Research complete with {len(results)} tasks")
    print(f"   2. ✅ Validation plan created with {len(validation_tasks)} tasks")
    print(f"   3. ⏭️  TODO: Run validator agent on validation plan")
    print(f"   4. ⏭️  TODO: Generate final report")
    
    return True


if __name__ == "__main__":
    import time
    
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)