"""
AUTO-UPDATE EVENTS WITH FREE GEMINI API
Searches Google daily, verifies with Gemini AI, updates automatically
100% FREE (no API costs!)
"""

import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

# ============================================
# CONFIGURATION
# ============================================

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'YOUR_GEMINI_API_KEY_HERE')
GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent'

# Search queries for different event types
SEARCH_QUERIES = [
    "Singapore events December 2025",
    "Singapore concerts 2025 2026",
    "Singapore festivals upcoming",
    "Singapore exhibitions now",
    "things to do Singapore this month",
    "Singapore free events",
    "Singapore Christmas events 2024",
    "Singapore family activities",
]

# ============================================
# WEB SEARCH FUNCTIONS
# ============================================

def search_google_events(query):
    """Search Google for Singapore events"""
    print(f"🔍 Searching: {query}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        
        for result in soup.find_all('div', class_='g'):
            try:
                title_elem = result.find('h3')
                snippet_elem = result.find('div', class_='VwiC3b')
                link_elem = result.find('a')
                
                if title_elem and link_elem:
                    title = title_elem.get_text()
                    link = link_elem.get('href', '')
                    snippet = snippet_elem.get_text() if snippet_elem else ''
                    
                    # Filter for Singapore event sites
                    if any(domain in link.lower() for domain in [
                        'marinabay', 'sentosa', 'esplanade', 'gardens', 
                        'sistic', 'ticketmaster', 'timeout', 'marinabaysands',
                        'mandai', 'rwsentosa', 'nhb.gov.sg', 'nationalgallery',
                        'thehoneycombers', 'livenation', 'eventbrite', 'peatix'
                    ]):
                        results.append({
                            'title': title,
                            'link': link,
                            'snippet': snippet,
                            'query': query
                        })
            except:
                continue
        
        return results[:5]  # Top 5 results
    
    except Exception as e:
        print(f"❌ Search error: {e}")
        return []


def verify_link(url):
    """Verify if a link is valid"""
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        return response.status_code == 200
    except:
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False


# ============================================
# GEMINI AI VERIFICATION
# ============================================

def verify_event_with_gemini(search_result):
    """
    Use Gemini AI to verify and structure event information
    Returns: Verified event dict or None if not valid
    """
    
    prompt = f"""You are an event verification AI for Singapore events. Analyze this search result:

SEARCH RESULT:
Title: {search_result['title']}
Link: {search_result['link']}
Snippet: {search_result['snippet']}

TASK:
1. Determine if this is a REAL, UPCOMING Singapore event (not past, not fake)
2. Extract: title, date, category, price, venue, description
3. Categorize as: concerts, arts, christmas, food, family, workshops, or festivals

IMPORTANT RULES:
- Only validate FUTURE events (December 2025 onwards)
- Must be in Singapore
- Must have clear date and venue
- Price should be numeric (0 for free)
- Reject if: past event, vague details, not Singapore

OUTPUT (JSON only, no other text):
{{
    "is_valid": true or false,
    "event": {{
        "title": "Event name (short, clear)",
        "date": "Date range (e.g. '13 Dec - 14 Dec' or 'Daily')",
        "category": "concerts/arts/christmas/food/family/workshops/festivals",
        "price": 0 or number,
        "venue": "Venue name",
        "description": "One clear sentence about the event",
        "link": "{search_result['link']}",
        "emoji": "relevant emoji"
    }},
    "reasoning": "Why valid or not"
}}

Respond with ONLY the JSON object, nothing else."""

    try:
        # Call Gemini API
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{
                    'parts': [{'text': prompt}]
                }]
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Gemini API error: {response.status_code}")
            return None
        
        data = response.json()
        
        # Extract text from Gemini response
        if 'candidates' in data and len(data['candidates']) > 0:
            text = data['candidates'][0]['content']['parts'][0]['text']
            
            # Clean up response
            text = text.strip()
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0]
            elif '```' in text:
                text = text.split('```')[1].split('```')[0]
            
            # Parse JSON
            result = json.loads(text.strip())
            
            if result.get('is_valid'):
                print(f"✅ Verified: {result['event']['title']}")
                return result['event']
            else:
                print(f"❌ Rejected: {result.get('reasoning', 'Invalid')}")
                return None
        else:
            print("❌ No response from Gemini")
            return None
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"❌ Gemini verification error: {e}")
        return None


# ============================================
# EVENT MANAGEMENT
# ============================================

def load_existing_events():
    """Load existing events from JSON file"""
    try:
        if os.path.exists('events.json'):
            with open('events.json', 'r') as f:
                return json.load(f)
        return []
    except:
        return []


def save_events(events):
    """Save events to JSON file"""
    with open('events.json', 'w') as f:
        json.dump(events, f, indent=2)
    print(f"💾 Saved {len(events)} events")


def deduplicate_events(events):
    """Remove duplicate events"""
    seen = set()
    unique = []
    
    for event in events:
        key = f"{event['title'].lower()}_{event['venue'].lower()}"
        if key not in seen:
            seen.add(key)
            unique.append(event)
    
    return unique


def remove_past_events(events):
    """Remove events that have already passed"""
    filtered = []
    
    for event in events:
        date_str = event['date'].lower()
        # Keep if Daily, Weekends, or mentions future month
        if any(word in date_str for word in ['daily', 'weekend', 'until']):
            filtered.append(event)
        elif any(month in date_str for month in ['dec', 'jan', 'feb', 'mar', 'apr', 'may', 'jun']):
            filtered.append(event)
    
    return filtered


# ============================================
# MAIN UPDATE FUNCTION
# ============================================

def daily_event_update():
    """Main function: Search, verify, and update events"""
    
    print("\n" + "="*60)
    print(f"🚀 STARTING DAILY EVENT UPDATE (FREE GEMINI)")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    # Load existing events
    existing_events = load_existing_events()
    print(f"📚 Loaded {len(existing_events)} existing events")
    
    # Remove past events
    existing_events = remove_past_events(existing_events)
    print(f"🗑️  After removing past: {len(existing_events)} events")
    
    new_events = []
    
    # Search for new events
    for query in SEARCH_QUERIES:
        print(f"\n🔍 Searching: {query}")
        
        results = search_google_events(query)
        print(f"Found {len(results)} potential results")
        
        for result in results:
            print(f"\n📄 Processing: {result['title'][:50]}...")
            
            # Verify link
            if not verify_link(result['link']):
                print(f"❌ Invalid link")
                continue
            
            # Verify with Gemini AI
            verified_event = verify_event_with_gemini(result)
            
            if verified_event:
                # Add unique ID
                verified_event['id'] = len(existing_events) + len(new_events) + 1
                new_events.append(verified_event)
            
            # Rate limiting (Gemini free tier: 60 requests/minute)
            time.sleep(1)
    
    print(f"\n✅ Found {len(new_events)} new verified events")
    
    # Merge and deduplicate
    all_events = existing_events + new_events
    all_events = deduplicate_events(all_events)
    
    print(f"📊 Total unique events: {len(all_events)}")
    
    # Save to file
    save_events(all_events)
    
    print("\n" + "="*60)
    print("✅ DAILY UPDATE COMPLETE")
    print("="*60 + "\n")
    
    return all_events


# ============================================
# RUN IT
# ============================================

if __name__ == "__main__":
    daily_event_update()
