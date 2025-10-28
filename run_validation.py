"""
Validation Runner - Executes validation plan and generates final report
Usage: python run_validation.py <validation_plan.json>
"""

import os
import sys
import json
import time
from pathlib import Path
from validation_agent import ValidationAgent, ValidationResult


def main():
    print("="*70)
    print("🔍 VALIDATOR AGENT - Executing Validation Plan")
    print("="*70)
    
    # Check API key
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("\n❌ Error: OPENROUTER_API_KEY not set")
        sys.exit(1)
    
    # Check for validation plan file
    if len(sys.argv) < 2:
        print("\n📖 Usage:")
        print("   python run_validation.py <validation_plan.json>")
        print("\nExample:")
        print("   python run_validation.py deck_validation_plan.json")
        sys.exit(1)
    
    plan_file = sys.argv[1]
    
    if not Path(plan_file).exists():
        print(f"\n❌ File not found: {plan_file}")
        sys.exit(1)
    
    # Load validation plan
    print(f"\n📂 Loading validation plan: {plan_file}")
    try:
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load plan: {e}")
        sys.exit(1)
    
    company_name = plan.get('company_name', 'Unknown')
    tasks = plan.get('validation_tasks', [])
    
    if not tasks:
        print("❌ No validation tasks found in plan")
        sys.exit(1)
    
    print(f"\n🏢 Company: {company_name}")
    print(f"📋 Total validation tasks: {len(tasks)}")
    
    # Show what will be validated
    print(f"\n📝 Claims to validate:")
    for i, task in enumerate(tasks[:5], 1):
        claim = task.get('claim', 'Unknown')
        print(f"   {i}. {claim[:70]}{'...' if len(claim) > 70 else ''}")
    if len(tasks) > 5:
        print(f"   ... and {len(tasks) - 5} more")
    
    # Cost estimate
    print(f"\n💰 Estimated cost: ${len(tasks) * 0.03:.2f}")
    print(f"⏱️  Estimated time: {len(tasks) * 15} seconds")
    
    confirm = input("\n⚠️  Proceed with validation? (y/n): ")
    if confirm.lower() != 'y':
        print("❌ Cancelled by user")
        sys.exit(0)
    
    # Initialize validator
    validator = ValidationAgent(api_key)
    
    # Execute validation
    print("\n" + "="*70)
    print("🚀 Starting Validation")
    print("="*70)
    
    start_time = time.time()
    validation_results = validator.execute_validation_plan(plan)
    elapsed_time = time.time() - start_time
    
    # Show quick summary
    print("\n" + "="*70)
    print("📊 VALIDATION SUMMARY")
    print("="*70)
    
    status_counts = {}
    for result in validation_results:
        status = result.status.value
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print(f"\n✅ Verified: {status_counts.get('verified', 0)}")
    print(f"❌ Contradicted: {status_counts.get('contradicted', 0)}")
    print(f"⚠️  Suspicious: {status_counts.get('suspicious', 0)}")
    print(f"❓ Unverified: {status_counts.get('unverified', 0)}")
    
    # Show critical issues immediately
    critical_results = [r for r in validation_results 
                       if r.severity.value in ['critical', 'high'] 
                       and r.status.value in ['contradicted', 'suspicious']]
    
    if critical_results:
        print(f"\n🚨 CRITICAL ISSUES FOUND ({len(critical_results)}):")
        for result in critical_results[:3]:
            print(f"\n   {result.severity.value.upper()}: {result.claim[:60]}...")
            print(f"   Status: {result.status.value}")
            print(f"   → {result.recommendation}")
    
    print(f"\n💰 Validation cost: ${validator.total_cost:.4f}")
    print(f"⏱️  Time taken: {elapsed_time:.1f} seconds")
    
    # Load original deck analysis if available
    deck_analysis_file = Path(plan_file).parent / f"{Path(plan_file).stem.replace('_validation_plan', '')}_deck_analysis.json"
    deck_analysis = None
    
    if deck_analysis_file.exists():
        try:
            with open(deck_analysis_file, 'r', encoding='utf-8') as f:
                deck_analysis = json.load(f)
                print(f"\n✅ Loaded original deck analysis")
        except Exception as e:
            print(f"⚠️  Could not load deck analysis: {e}")
    
    # Generate comprehensive validation report
    print("\n" + "="*70)
    print("📋 GENERATING VALIDATION REPORT")
    print("="*70)
    
    report = validator.generate_validation_report(
        company_name=company_name,
        validation_results=validation_results,
        deck_analysis=deck_analysis
    )
    
    # Save validation report
    output_file = Path(plan_file).parent / f"{Path(plan_file).stem.replace('_validation_plan', '')}_validation_report.json"
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"✅ Validation report saved: {output_file}")
    except Exception as e:
        print(f"❌ Failed to save report: {e}")
    
    # Generate human-readable markdown report
    print("\n" + "="*70)
    print("📄 GENERATING MARKDOWN REPORT")
    print("="*70)
    
    markdown_file = Path(plan_file).parent / f"{Path(plan_file).stem.replace('_validation_plan', '')}_FINAL_REPORT.md"
    
    try:
        markdown_content = generate_markdown_report(report, deck_analysis)
        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"✅ Final markdown report saved: {markdown_file}")
    except Exception as e:
        print(f"❌ Failed to generate markdown: {e}")
    
    # Final summary
    print("\n" + "="*70)
    print("✅ VALIDATION COMPLETE")
    print("="*70)
    
    print(f"\n🏢 Company: {company_name}")
    print(f"📊 Validation tasks completed: {len(validation_results)}")
    print(f"💰 Total cost: ${validator.total_cost:.4f}")
    
    print(f"\n🎯 INVESTMENT RECOMMENDATION:")
    print(f"   {report.investment_recommendation}")
    
    print(f"\n📁 Output files:")
    print(f"   • {output_file}")
    print(f"   • {markdown_file}")
    
    # Color-code the recommendation
    if "PASS" in report.investment_recommendation:
        print(f"\n✅ GREEN LIGHT - Claims verified, proceed with diligence")
    elif "CAUTION" in report.investment_recommendation:
        print(f"\n⚠️  YELLOW LIGHT - Concerns identified, deeper investigation needed")
    else:
        print(f"\n🛑 RED LIGHT - Critical issues found, high risk")
    
    return True


def generate_markdown_report(report: ValidationResult, deck_analysis: dict = None) -> str:
    """Generate human-readable markdown report"""
    
    md = f"""# Investment Due Diligence Report
## {report.company_name}

---

## 🎯 Executive Summary

**Investment Recommendation:** `{report.investment_recommendation}`

### Quick Stats
- **Claims Verified:** {report.verified_count}/{report.total_claims_checked} ({report.verified_count/max(1,report.total_claims_checked)*100:.0f}%)
- **Contradicted Claims:** {report.contradicted_count}
- **Suspicious Findings:** {report.suspicious_count}
- **Unverified Claims:** {report.unverified_count}
- **Critical Issues:** {len(report.critical_issues)}

---

## 📊 Overall Assessment

{report.overall_assessment}

---

"""
    
    # Add company context if available
    if deck_analysis:
        md += f"""## 🏢 Company Overview

**Stage:** {deck_analysis.get('stage', 'Unknown')}  
**Funding Ask:** {deck_analysis.get('funding_ask', 'Not specified')}  
**Website:** {deck_analysis.get('website', 'Not provided')}

**Problem:** {deck_analysis.get('problem', 'Not specified')}

**Solution:** {deck_analysis.get('solution', 'Not specified')}

**Founders:** {', '.join(deck_analysis.get('founders', ['Not specified']))}

---

"""
    
    # Critical issues section
    if report.critical_issues:
        md += f"""## 🚨 Critical Issues ({len(report.critical_issues)})

"""
        for i, issue in enumerate(report.critical_issues, 1):
            severity_emoji = {'critical': '🔴', 'high': '🟡', 'medium': '🟢', 'low': '⚪'}
            status_emoji = {'contradicted': '❌', 'suspicious': '⚠️', 'unverified': '❓', 'verified': '✅'}
            
            md += f"""### {i}. {severity_emoji.get(issue['severity'], '•')} {issue['claim']}

**Status:** {status_emoji.get(issue['status'], '•')} {issue['status'].upper()}  
**Severity:** {issue['severity'].upper()}

**Analysis:**  
{issue['reasoning']}

**Recommendation:**  
{issue['recommendation']}

---

"""
    
    # Detailed validation results
    md += f"""## 📋 Detailed Validation Results

"""
    
    # Group by status
    by_status = {}
    for result in report.validation_results:
        status = result.status.value
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(result)
    
    # Show contradicted first
    if 'contradicted' in by_status:
        md += f"""### ❌ Contradicted Claims ({len(by_status['contradicted'])})

"""
        for result in by_status['contradicted']:
            md += format_validation_detail(result)
    
    # Then suspicious
    if 'suspicious' in by_status:
        md += f"""### ⚠️  Suspicious Claims ({len(by_status['suspicious'])})

"""
        for result in by_status['suspicious']:
            md += format_validation_detail(result)
    
    # Then unverified
    if 'unverified' in by_status:
        md += f"""### ❓ Unverified Claims ({len(by_status['unverified'])})

"""
        for result in by_status['unverified'][:5]:  # Limit to 5
            md += format_validation_detail(result)
        
        if len(by_status['unverified']) > 5:
            md += f"\n*...and {len(by_status['unverified']) - 5} more unverified claims*\n\n"
    
    # Finally verified
    if 'verified' in by_status:
        md += f"""### ✅ Verified Claims ({len(by_status['verified'])})

"""
        for result in by_status['verified'][:5]:  # Limit to 5
            md += format_validation_detail(result, brief=True)
        
        if len(by_status['verified']) > 5:
            md += f"\n*...and {len(by_status['verified']) - 5} more verified claims*\n\n"
    
    # Footer
    md += f"""---

## 📝 Notes

This report was generated by an automated validation system. All findings should be reviewed by investment professionals before making final decisions.

**Report Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}

---
"""
    
    return md


def format_validation_detail(result, brief: bool = False) -> str:
    """Format a single validation result for markdown"""
    
    md = f"""#### {result.claim}

**Confidence:** {result.confidence:.0%}  
**Severity:** {result.severity.value.upper()}

"""
    
    if not brief:
        if result.evidence_for:
            md += "**Evidence Supporting:**\n"
            for evidence in result.evidence_for[:3]:
                md += f"- {evidence}\n"
            md += "\n"
        
        if result.evidence_against:
            md += "**Evidence Against:**\n"
            for evidence in result.evidence_against:
                md += f"- {evidence}\n"
            md += "\n"
        
        md += f"**Analysis:** {result.reasoning}\n\n"
    
    md += f"**Recommendation:** {result.recommendation}\n\n---\n\n"
    
    return md


if __name__ == "__main__":
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