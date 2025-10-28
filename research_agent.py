"""
Research Agent - Executes research tasks using Selenium
Handles blocked sites, dynamic content, and anti-bot measures
"""

import time
import json
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
import requests
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()

@dataclass
class ResearchResult:
    """Result from a single research task"""
    task_id: str
    query: str
    status: str  # success, partial, failed
    sources: List[Dict]  # [{url, title, content, scraped_at}]
    summary: str
    key_findings: List[str]
    red_flags: List[str]
    confidence_score: float  # 0-1
    
    def to_dict(self):
        return asdict(self)

@dataclass
class ValidationTask:
    """Task for validator agent to verify"""
    validation_id: str
    claim: str
    source: str  # from pitch deck
    evidence: List[Dict]  # research findings
    requires_verification: bool
    
    def to_dict(self):
        return asdict(self)


class SeleniumScraper:
    """
    Smart web scraper using Selenium
    Handles JavaScript, anti-bot detection, rate limiting
    """
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        
    def _init_driver(self):
        """Initialize Chrome driver with anti-detection measures"""
        if self.driver:
            return
        
        options = Options()
        
        if self.headless:
            options.add_argument('--headless=new')  # New headless mode
        
        # Anti-detection measures
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # More realistic browser fingerprint (updated Chrome version and more details)
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        
        # Additional anti-detection measures
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        options.add_argument('--disable-site-isolation-trials')
        
        # Mimic real browser behavior
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--start-maximized')
        
        # Language and locale
        options.add_argument('--lang=en-US')
        options.add_experimental_option('prefs', {
            'intl.accept_languages': 'en-US,en;q=0.9',
            'profile.default_content_setting_values.notifications': 2,
            'credentials_enable_service': False,
            'profile.password_manager_enabled': False
        })
        
        try:
            self.driver = webdriver.Chrome(options=options)
            
            # Override navigator.webdriver flag
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Override other detection vectors
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                "platform": "Windows",
                "acceptLanguage": "en-US,en;q=0.9"
            })
            
            # Mask automation indicators
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)
            
            print("✅ Selenium driver initialized with enhanced anti-detection")
        except Exception as e:
            print(f"⚠️  Selenium driver failed: {e}")
            print("   Falling back to requests-based scraping")
            self.driver = None
    
    def scrape(self, url: str, wait_for: Optional[str] = None, max_wait: int = 10) -> Optional[Dict]:
        """
        Scrape URL with Selenium
        
        Args:
            url: URL to scrape
            wait_for: CSS selector to wait for (optional)
            max_wait: Max seconds to wait for element
        
        Returns:
            {url, title, content, success}
        """
        # Try Selenium first
        if self.driver is None:
            self._init_driver()
        
        if self.driver:
            try:
                print(f"   🌐 Loading: {url[:60]}...")
                self.driver.get(url)
                
                # Wait for specific element if provided
                if wait_for:
                    WebDriverWait(self.driver, max_wait).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_for))
                    )
                else:
                    # Default wait for body
                    time.sleep(2)  # Let JavaScript execute
                
                # Get page source
                page_source = self.driver.page_source
                title = self.driver.title
                
                # Parse with BeautifulSoup for cleaning
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Remove unwanted elements
                for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript']):
                    tag.decompose()
                
                # Extract clean text
                text = soup.get_text(separator='\n', strip=True)
                
                # Clean whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)
                
                print(f"   ✅ Scraped {len(text)} characters")
                
                return {
                    'url': url,
                    'title': title,
                    'content': text[:5000],  # Limit content
                    'success': True,
                    'method': 'selenium'
                }
                
            except TimeoutException:
                print(f"   ⏱️  Timeout waiting for page to load")
            except WebDriverException as e:
                print(f"   ⚠️  Selenium error: {str(e)[:50]}")
            except Exception as e:
                print(f"   ❌ Unexpected error: {str(e)[:50]}")
        
        # Fallback to requests if Selenium fails
        return self._fallback_scrape(url)
    
    def _fallback_scrape(self, url: str) -> Optional[Dict]:
        """Fallback to basic requests if Selenium fails"""
        try:
            print(f"   📡 Fallback scraping: {url[:60]}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Clean content
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            text = soup.get_text(separator='\n', strip=True)
            title = soup.title.string if soup.title else "No title"
            
            print(f"   ✅ Fallback scraped {len(text)} characters")
            
            return {
                'url': url,
                'title': title,
                'content': text[:5000],
                'success': True,
                'method': 'requests'
            }
            
        except Exception as e:
            print(f"   ❌ Fallback failed: {str(e)[:50]}")
            return {
                'url': url,
                'title': 'Failed to load',
                'content': '',
                'success': False,
                'method': 'none'
            }
    
    def search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search DuckDuckGo and return results"""
        try:
            print(f"   🔍 Searching: {query}")
            
            search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.post(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for result in soup.find_all('div', class_='result')[:max_results]:
                title_elem = result.find('a', class_='result__a')
                snippet_elem = result.find('a', class_='result__snippet')
                
                if title_elem:
                    results.append({
                        'title': title_elem.get_text(strip=True),
                        'url': title_elem.get('href', ''),
                        'snippet': snippet_elem.get_text(strip=True) if snippet_elem else ''
                    })
            
            print(f"   ✅ Found {len(results)} results")
            return results
            
        except Exception as e:
            print(f"   ❌ Search failed: {e}")
            return []
    
    def close(self):
        """Close browser"""
        if self.driver:
            self.driver.quit()
            self.driver = None

class ResearchAgent:
    """
    Research Agent - Executes research tasks
    Uses Selenium for deep web research
    Creates validation tasks for claims
    """
    
    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-haiku"):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.model = model
        self.scraper = SeleniumScraper(headless=True)
        self.total_cost = 0.0
        
    def execute_task(self, task: Dict) -> ResearchResult:
        """
        Execute a single research task
        
        Args:
            task: Task dict from orchestrator with {task_id, query, context, reasoning}
        
        Returns:
            ResearchResult with findings
        """
        task_id = task['task_id']
        query = task['query']
        context = task.get('context', '')
        
        print(f"\n🔬 [{task_id}] Executing: {query}")
        
        # Step 1: Search for information
        search_results = self.scraper.search_duckduckgo(query, max_results=5)
        
        if not search_results:
            print(f"   ⚠️  No search results found")
            # print(f"   📊 REASON: {search_status}")
            return ResearchResult(
                task_id=task_id,
                query=query,
                status='failed',
                sources=[],
                summary="No information found",
                key_findings=[],
                red_flags=["No search results - company may not exist or have no online presence"],
                confidence_score=0.0
            )
        
        # Step 2: Scrape top results
        sources = []
        for i, result in enumerate(search_results[:3], 1):  # Scrape top 3
            print(f"   [{i}/{len(search_results[:3])}] Scraping: {result['title'][:60]}...")
            
            scraped = self.scraper.scrape(result['url'])
            
            if scraped and scraped['success'] and len(scraped['content']) > 100:
                sources.append({
                    'url': scraped['url'],
                    'title': scraped['title'],
                    'snippet': result['snippet'],
                    'content': scraped['content'][:3000],  # Limit for LLM
                    'method': scraped['method']
                })
            else:
                # Still save snippet even if scraping failed
                sources.append({
                    'url': result['url'],
                    'title': result['title'],
                    'snippet': result['snippet'],
                    'content': '',
                    'method': 'none'
                })
            
            time.sleep(1)  # Rate limiting
        
        # Step 3: Analyze findings with LLM
        analysis = self._analyze_findings(query, context, sources)
        
        # Step 4: Create research result
        result = ResearchResult(
            task_id=task_id,
            query=query,
            status='success' if sources else 'partial',
            sources=sources,
            summary=analysis.get('summary', 'No analysis available'),
            key_findings=analysis.get('key_findings', []),
            red_flags=analysis.get('red_flags', []),
            confidence_score=analysis.get('confidence_score', 0.5)
        )
        
        print(f"   ✅ Research complete - Confidence: {result.confidence_score:.1%}")
        
        return result
    
    def _analyze_findings(self, query: str, context: str, sources: List[Dict]) -> Dict:
        """Use LLM to analyze research findings"""
        
        # Prepare sources text
        sources_text = ""
        for i, source in enumerate(sources, 1):
            sources_text += f"\n### Source {i}: {source['title']}\n"
            sources_text += f"URL: {source['url']}\n"
            if source['snippet']:
                sources_text += f"Snippet: {source['snippet']}\n"
            if source['content']:
                sources_text += f"Content: {source['content'][:1500]}...\n"
            sources_text += "\n"
        
        prompt = f"""You are a research analyst for a VC firm. Analyze these research findings.

RESEARCH QUERY: {query}
CONTEXT: {context}

SOURCES FOUND:
{sources_text[:6000]}

Analyze the findings and return a JSON object:
{{
  "summary": "2-3 sentence summary of what was found",
  "key_findings": ["finding 1", "finding 2", "finding 3"],
  "red_flags": ["any concerns or warning signs"],
  "confidence_score": 0.0-1.0,  How confident are you in these findings?
  "validation_needed": ["specific claims that need to be verified"]
}}

Focus on:
- Factual information that answers the query
- Any discrepancies between sources
- Missing information that's expected
- Signs of legitimacy or red flags

Return ONLY valid JSON."""

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
            
            analysis = json.loads(content)
            
            # Track cost
            tokens_used = len(prompt) // 4 + 800
            self.total_cost += (tokens_used / 1000) * 0.003
            
            return analysis
            
        except Exception as e:
            print(f"   ⚠️  LLM analysis failed: {e}")
            return {
                'summary': 'Analysis failed',
                'key_findings': [],
                'red_flags': [],
                'confidence_score': 0.3,
                'validation_needed': []
            }
    
    def create_validation_plan(self, research_results: List[ResearchResult], 
                              deck_analysis: Dict) -> List[ValidationTask]:
        """
        Create validation tasks based on research findings
        
        Args:
            research_results: All research results
            deck_analysis: Original deck analysis from orchestrator
        
        Returns:
            List of validation tasks for validator agent
        """
        print("\n📋 Creating validation plan...")
        
        validation_tasks = []
        task_counter = 0
        
        # Extract claims from deck
        claims = deck_analysis.get('claims', [])
        
        for claim in claims:
            task_counter += 1
            
            # Find relevant research evidence
            evidence = []
            for result in research_results:
                # Check if research is relevant to this claim
                if any(keyword in result.query.lower() for keyword in claim.lower().split()[:3]):
                    evidence.append({
                        'task_id': result.task_id,
                        'query': result.query,
                        'findings': result.key_findings,
                        'confidence': result.confidence_score
                    })
            
            validation_tasks.append(ValidationTask(
                validation_id=f"V{task_counter:03d}",
                claim=claim,
                source="pitch_deck",
                evidence=evidence,
                requires_verification=True
            ))
        
        # Add validation for founder backgrounds
        founders = deck_analysis.get('founders', [])
        for founder in founders:
            task_counter += 1
            
            # Find research about this founder
            evidence = []
            for result in research_results:
                if founder.lower() in result.query.lower():
                    evidence.append({
                        'task_id': result.task_id,
                        'query': result.query,
                        'findings': result.key_findings,
                        'red_flags': result.red_flags,
                        'confidence': result.confidence_score
                    })
            
            validation_tasks.append(ValidationTask(
                validation_id=f"V{task_counter:03d}",
                claim=f"Founder {founder} has relevant background",
                source="pitch_deck",
                evidence=evidence,
                requires_verification=True
            ))
        
        print(f"✅ Created {len(validation_tasks)} validation tasks")
        
        return validation_tasks
    
    def cleanup(self):
        """Clean up resources"""
        self.scraper.close()


# Test function
if __name__ == "__main__":
    import sys
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Set OPENROUTER_API_KEY")
        sys.exit(1)
    
    # Test with a simple task
    test_task = {
        'task_id': 'TEST001',
        'query': 'Stripe payment processing company crunchbase funding',
        'context': 'Testing research agent',
        'reasoning': 'Verify research agent works'
    }
    
    print("🧪 Testing Research Agent\n")
    
    agent = ResearchAgent(api_key)
    result = agent.execute_task(test_task)
    
    print("\n" + "="*60)
    print("📊 RESEARCH RESULT")
    print("="*60)
    print(f"Status: {result.status}")
    print(f"Sources found: {len(result.sources)}")
    print(f"Confidence: {result.confidence_score:.1%}")
    print(f"\nSummary: {result.summary}")
    print(f"\nKey Findings:")
    for finding in result.key_findings:
        print(f"  • {finding}")
    
    if result.red_flags:
        print(f"\nRed Flags:")
        for flag in result.red_flags:
            print(f"  ⚠️  {flag}")
    
    agent.cleanup()
    
    print(f"\n💰 Total cost: ${agent.total_cost:.4f}")
