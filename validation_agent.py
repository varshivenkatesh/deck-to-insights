"""
Validator Agent - Cross-references claims with research findings
Uses reasoning to identify discrepancies and verify accuracy
"""

import json
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from openai import OpenAI
from enum import Enum
import os
from dotenv import load_dotenv
load_dotenv()


class ValidationStatus(Enum):
    VERIFIED = "verified"           # Claim is supported by evidence
    CONTRADICTED = "contradicted"   # Claim directly conflicts with evidence
    UNVERIFIED = "unverified"       # Insufficient evidence to verify
    SUSPICIOUS = "suspicious"       # Evidence raises concerns


class Severity(Enum):
    CRITICAL = "critical"    # Deal breaker
    HIGH = "high"           # Major concern
    MEDIUM = "medium"       # Notable issue
    LOW = "low"            # Minor discrepancy


@dataclass
class ValidationResult:
    """Result from validating a single claim"""
    validation_id: str
    claim: str
    status: ValidationStatus
    severity: Severity
    evidence_for: List[str]      # Evidence supporting the claim
    evidence_against: List[str]  # Evidence contradicting the claim
    reasoning: str               # LLM's reasoning process
    confidence: float            # 0-1 confidence in validation
    recommendation: str          # What to do about this
    
    def to_dict(self):
        return {
            'validation_id': self.validation_id,
            'claim': self.claim,
            'status': self.status.value,
            'severity': self.severity.value,
            'evidence_for': self.evidence_for,
            'evidence_against': self.evidence_against,
            'reasoning': self.reasoning,
            'confidence': self.confidence,
            'recommendation': self.recommendation
        }


@dataclass
class ValidationReport:
    """Complete validation report"""
    company_name: str
    total_claims_checked: int
    verified_count: int
    contradicted_count: int
    unverified_count: int
    suspicious_count: int
    critical_issues: List[Dict]
    validation_results: List[ValidationResult]
    overall_assessment: str
    investment_recommendation: str
    
    def to_dict(self):
        return {
            'company_name': self.company_name,
            'summary': {
                'total_claims_checked': self.total_claims_checked,
                'verified': self.verified_count,
                'contradicted': self.contradicted_count,
                'unverified': self.unverified_count,
                'suspicious': self.suspicious_count
            },
            'critical_issues': self.critical_issues,
            'validation_results': [v.to_dict() for v in self.validation_results],
            'overall_assessment': self.overall_assessment,
            'investment_recommendation': self.investment_recommendation
        }


class ValidationAgent:
    """
    Validator Agent - The Truth Checker
    
    Responsibilities:
    1. Cross-reference pitch deck claims with research findings
    2. Identify discrepancies and inconsistencies
    3. Assess severity of any issues found
    4. Provide recommendations on each claim
    """
    
    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-haiku"):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.model = model
        self.total_cost = 0.0
    
    def validate_claim(self, validation_task: Dict) -> ValidationResult:
        """
        Validate a single claim against research evidence
        
        Args:
            validation_task: {
                'validation_id': 'V001',
                'claim': 'The claim to verify',
                'source': 'pitch_deck',
                'evidence': [{research findings}],
                'requires_verification': True
            }
        
        Returns:
            ValidationResult with detailed analysis
        """
        validation_id = validation_task['validation_id']
        claim = validation_task['claim']
        evidence = validation_task['evidence']
        
        print(f"\n🔍 Validating: {claim[:70]}...")
        
        # Prepare evidence context
        evidence_text = self._format_evidence(evidence)
        
        # Use LLM to analyze claim against evidence
        prompt = f"""You are a fact-checker for an investment firm. Validate this claim against research evidence.

CLAIM TO VERIFY:
"{claim}"

RESEARCH EVIDENCE:
{evidence_text}

Analyze whether the claim is supported, contradicted, or unverifiable based on the evidence.

Return a JSON object:
{{
  "status": "verified|contradicted|unverified|suspicious",
  "severity": "critical|high|medium|low",
  "evidence_for": ["specific evidence supporting claim"],
  "evidence_against": ["specific evidence contradicting claim"],
  "reasoning": "detailed explanation of your analysis process",
  "confidence": 0.0-1.0,
  "recommendation": "what investor should do about this finding"
}}

IMPORTANT GUIDELINES:
- "verified": Strong evidence supports the claim (>70% confidence)
- "contradicted": Evidence directly conflicts with claim
- "unverified": Not enough evidence to confirm or deny
- "suspicious": Evidence raises concerns even if not direct contradiction

Severity levels:
- "critical": Could be a deal-breaker (false claims, major discrepancies)
- "high": Significant concern requiring investigation
- "medium": Notable issue but not immediately disqualifying
- "low": Minor discrepancy or missing context

Be thorough but fair. Strong claims require strong evidence.
Return ONLY valid JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            
            # Track cost
            tokens_used = len(prompt) // 4 + 1000
            self.total_cost += (tokens_used / 1000) * 0.003
            
            # Create validation result
            result = ValidationResult(
                validation_id=validation_id,
                claim=claim,
                status=ValidationStatus(analysis['status']),
                severity=Severity(analysis['severity']),
                evidence_for=analysis['evidence_for'],
                evidence_against=analysis['evidence_against'],
                reasoning=analysis['reasoning'],
                confidence=analysis['confidence'],
                recommendation=analysis['recommendation']
            )
            
            # Print summary
            status_emoji = {
                'verified': '✅',
                'contradicted': '❌',
                'unverified': '❓',
                'suspicious': '⚠️'
            }
            print(f"   {status_emoji[result.status.value]} {result.status.value.upper()} "
                  f"(confidence: {result.confidence:.0%})")
            
            if result.status in [ValidationStatus.CONTRADICTED, ValidationStatus.SUSPICIOUS]:
                print(f"   🚨 {result.severity.value.upper()} severity issue detected")
            
            return result
            
        except Exception as e:
            print(f"   ❌ Validation failed: {e}")
            
            # Return failed validation
            return ValidationResult(
                validation_id=validation_id,
                claim=claim,
                status=ValidationStatus.UNVERIFIED,
                severity=Severity.MEDIUM,
                evidence_for=[],
                evidence_against=[],
                reasoning=f"Validation failed due to error: {str(e)}",
                confidence=0.0,
                recommendation="Manual review required - automated validation failed"
            )
    
    def _format_evidence(self, evidence: List[Dict]) -> str:
        """Format research evidence for LLM analysis"""
        if not evidence:
            return "No research evidence found for this claim."
        
        formatted = ""
        for i, ev in enumerate(evidence, 1):
            formatted += f"\n--- Evidence {i} ---\n"
            formatted += f"Research Query: {ev.get('query', 'Unknown')}\n"
            formatted += f"Confidence: {ev.get('confidence', 0):.0%}\n"
            
            if 'findings' in ev and ev['findings']:
                formatted += "Findings:\n"
                for finding in ev['findings'][:5]:  # Limit to top 5
                    formatted += f"  • {finding}\n"
            
            if 'red_flags' in ev and ev['red_flags']:
                formatted += "Red Flags:\n"
                for flag in ev['red_flags']:
                    formatted += f"  ⚠️  {flag}\n"
            
            formatted += "\n"
        
        return formatted[:4000]  # Limit total length
    
    def execute_validation_plan(self, validation_plan: Dict) -> List[ValidationResult]:
        """
        Execute all validation tasks in a plan
        
        Args:
            validation_plan: {
                'company_name': 'CompanyX',
                'validation_tasks': [list of tasks],
                'total_tasks': N
            }
        
        Returns:
            List of validation results
        """
        company_name = validation_plan['company_name']
        tasks = validation_plan['validation_tasks']
        
        print("\n" + "="*70)
        print(f"🔎 VALIDATOR AGENT - Validating {company_name}")
        print("="*70)
        print(f"📋 Total validation tasks: {len(tasks)}")
        
        results = []
        
        for i, task in enumerate(tasks, 1):
            print(f"\n{'─'*70}")
            print(f"Task {i}/{len(tasks)}")
            print(f"{'─'*70}")
            
            result = self.validate_claim(task)
            results.append(result)
            
            # Small delay to avoid rate limiting
            import time
            time.sleep(0.5)
        
        print(f"\n💰 Validation cost: ${self.total_cost:.4f}")
        
        return results
    
    def generate_validation_report(self, 
                                   company_name: str,
                                   validation_results: List[ValidationResult],
                                   deck_analysis: Optional[Dict] = None) -> ValidationReport:
        """
        Generate comprehensive validation report with investment recommendation
        
        Args:
            company_name: Company name
            validation_results: All validation results
            deck_analysis: Original deck analysis (optional)
        
        Returns:
            ValidationReport with summary and recommendations
        """
        print("\n" + "="*70)
        print("📊 GENERATING VALIDATION REPORT")
        print("="*70)
        
        # Count results by status
        verified = [r for r in validation_results if r.status == ValidationStatus.VERIFIED]
        contradicted = [r for r in validation_results if r.status == ValidationStatus.CONTRADICTED]
        unverified = [r for r in validation_results if r.status == ValidationStatus.UNVERIFIED]
        suspicious = [r for r in validation_results if r.status == ValidationStatus.SUSPICIOUS]
        
        # Identify critical issues
        critical_issues = []
        for result in validation_results:
            if result.severity in [Severity.CRITICAL, Severity.HIGH]:
                if result.status in [ValidationStatus.CONTRADICTED, ValidationStatus.SUSPICIOUS]:
                    critical_issues.append({
                        'claim': result.claim,
                        'status': result.status.value,
                        'severity': result.severity.value,
                        'reasoning': result.reasoning,
                        'recommendation': result.recommendation
                    })
        
        # Generate overall assessment using LLM
        assessment_data = {
            'company_name': company_name,
            'total_claims': len(validation_results),
            'verified': len(verified),
            'contradicted': len(contradicted),
            'suspicious': len(suspicious),
            'unverified': len(unverified),
            'critical_issues_count': len(critical_issues),
            'critical_issues': critical_issues[:5]  # Top 5
        }
        
        overall_assessment, investment_rec = self._generate_llm_assessment(assessment_data, deck_analysis)
        
        report = ValidationReport(
            company_name=company_name,
            total_claims_checked=len(validation_results),
            verified_count=len(verified),
            contradicted_count=len(contradicted),
            unverified_count=len(unverified),
            suspicious_count=len(suspicious),
            critical_issues=critical_issues,
            validation_results=validation_results,
            overall_assessment=overall_assessment,
            investment_recommendation=investment_rec
        )
        
        print("✅ Validation report generated")
        
        return report
    
    def _generate_llm_assessment(self, validation_summary: Dict, deck_analysis: Optional[Dict]) -> tuple:
        """Use LLM to generate overall assessment and recommendation"""
        
        context = ""
        if deck_analysis:
            context = f"""
COMPANY CONTEXT:
- Name: {deck_analysis.get('company_name', 'Unknown')}
- Stage: {deck_analysis.get('stage', 'Unknown')}
- Problem: {deck_analysis.get('problem', 'Not specified')}
- Solution: {deck_analysis.get('solution', 'Not specified')}
- Funding Ask: {deck_analysis.get('funding_ask', 'Not specified')}
"""
        
        prompt = f"""You are an investment analyst writing a validation report summary.

{context}

VALIDATION RESULTS:
- Total claims checked: {validation_summary['total_claims']}
- Verified: {validation_summary['verified']} ({validation_summary['verified']/max(1,validation_summary['total_claims'])*100:.0f}%)
- Contradicted: {validation_summary['contradicted']}
- Suspicious: {validation_summary['suspicious']}
- Unverified: {validation_summary['unverified']}
- Critical issues found: {validation_summary['critical_issues_count']}

CRITICAL ISSUES:
{json.dumps(validation_summary['critical_issues'], indent=2)}

Write a JSON report:
{{
  "overall_assessment": "2-3 paragraph assessment of validation findings. Be balanced but honest about concerns.",
  "investment_recommendation": "PASS|PROCEED_WITH_CAUTION|REJECT with brief justification"
}}

Guidelines:
- PASS: Most claims verified, no critical issues, minor concerns are addressable
- PROCEED_WITH_CAUTION: Some concerns but company may still be viable with more diligence
- REJECT: Critical issues like false claims, missing founders, or fundamental problems

Be direct and actionable. VCs need clear recommendations.
Return ONLY valid JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800
            )
            
            content = response.choices[0].message.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # Track cost
            tokens_used = len(prompt) // 4 + 800
            self.total_cost += (tokens_used / 1000) * 0.003
            
            return result['overall_assessment'], result['investment_recommendation']
            
        except Exception as e:
            print(f"⚠️  Failed to generate LLM assessment: {e}")
            
            # Fallback to rule-based assessment
            if validation_summary['contradicted'] > 0 or validation_summary['critical_issues_count'] > 2:
                rec = "REJECT - Multiple critical issues or contradicted claims"
            elif validation_summary['suspicious'] > 0 or validation_summary['critical_issues_count'] > 0:
                rec = "PROCEED_WITH_CAUTION - Some concerns require deeper investigation"
            else:
                rec = "PASS - Claims appear valid based on available evidence"
            
            assessment = f"Validation checked {validation_summary['total_claims']} claims. " \
                        f"{validation_summary['verified']} were verified, " \
                        f"{validation_summary['contradicted']} were contradicted, " \
                        f"and {validation_summary['unverified']} could not be verified with available evidence."
            
            return assessment, rec


# Test function
if __name__ == "__main__":
    import sys
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Set OPENROUTER_API_KEY")
        sys.exit(1)
    
    # Create test validation task
    test_task = {
        'validation_id': 'V001',
        'claim': 'Company has 10,000 active users',
        'source': 'pitch_deck',
        'evidence': [
            {
                'task_id': 'T001',
                'query': 'Company user count verification',
                'findings': [
                    'LinkedIn post from CEO mentions reaching 8,500 users last month',
                    'TechCrunch article from 2 weeks ago cites 9,200 users',
                    'Company blog post claims "nearly 10k users"'
                ],
                'red_flags': [],
                'confidence': 0.75
            }
        ],
        'requires_verification': True
    }
    
    print("🧪 Testing Validator Agent\n")
    
    validator = ValidationAgent(api_key)
    result = validator.validate_claim(test_task)
    
    print("\n" + "="*60)
    print("📊 VALIDATION RESULT")
    print("="*60)
    print(json.dumps(result.to_dict(), indent=2))
    
    print(f"\n💰 Total cost: ${validator.total_cost:.4f}")