#!/usr/bin/env python3
"""
Test the improved filtering logic on existing database data.
"""
from database_utils import get_db_session
from sqlalchemy import text

def test_improved_url_filtering():
    """Test the improved URL filtering on existing data."""
    
    # Enhanced exclude patterns (copied from our improvements)
    exclude_patterns = [
        # Original patterns
        '/blog/', '/article/', '/news/', '/press/', '/about/', '/contact/',
        '/privacy/', '/terms/', '/careers/', '/jobs/', '/login/', '/signup/',
        '/demo/', '/trial/', '/pricing/', '/product/', '/solutions/',
        '/learn/', '/course/', '/tutorial/', '/guide/', '/documentation/',
        '/api/', '/docs/', '/help/', '/support/', '/faq/',
        '/category/', '/tag/', '/author/', '/search/', '/sitemap/',
        '.pdf', '.doc', '.ppt', '.zip', '.jpg', '.png', '.gif',
        '/user/', '/profile/', '/account/', '/dashboard/', '/users/',
        '/viewprofilepage/', '/user-id/', '/sign_up', '/signup', '/register/',
        '/business/', '/enterprise/', '/services/', '/consulting/',
        '/use-case/', '/use_case/', '/usecase/', '/case-study/', '/case_study/',
        '/form/', '/forms/', '/subscribe/', '/subscription/',
        '/newsletter/', '/download/', '/resource/', '/resources/',
        '/white-paper/', '/whitepaper/', '/e-book/', '/ebook/',
        '/hub/', '/platform/', '/software/', '/app/', '/applications/',
        '/training/', '/certification/', '/certifications/',
        '/discussion/', '/discussions/', '/forum/', '/forums/',
        '/community/', '/bd-p/', '/t5/', '/messagepage/',
        '/pricing/', '/plans/', '/features/', '/benefits/',
        '/customer/', '/customers/', '/success/', '/testimonials/',
        '/partners/', '/partnership/', '/vendor/',
        '/appdynamics/', '/splunk/', '/databricks/',
        '/artificial-intelligence/', '/ai-', '/machine-learning/',
        '/security/', '/observability/', '/monitoring/',
        '/en_us/', '/tips/', '/learn/', '/industry/', '/industries/',
        '/global-impact/', '/leadership/', '/site-map/',
        '/get-started/', '/migration/', '/digital-resilience/',
        '/data-management/', '/all-use-cases/', '/virtual-event-',
        '/push-notifications/', '/virtual-events-vocabulary/',
        '/hybrid-webinars/', '/employer-branding/',
        '/company-milestone-events/', '/product-launch/',
        '/sales-kickoff/', '/conference-summits/',
        'trustpilot.com', 'review/', '/reviews/',
        '?redirect=', '?generated_by=', '?hash=', '?q=',
        '&redirect=', '&generated_by=', '&hash=', '&q=',
        
        # NEW patterns from our analysis
        'status.', '/status', '/status/', 'statuspage.',
        '/organizer/', '/industry/', '/service/', '/ticketing',
        'event-industry', 'food-drink-event', 'event ticketing',
        'community.databricks.com/t5/user/',
        '/viewprofilepage/user-id/',
        '/blog/author/', '/blog/security', '/blog/industries',
        '/form/splunk-blogs-subscribe',
        '/airmeet.com/hub/blog/', 'status.airmeet.com',
        '/polls-and-surveys', '/hybrid-webinars',
        '/organizer/event-industry/', '/food-drink-event-ticketing'
    ]
    
    session = get_db_session()
    
    # Get all conferences
    result = session.execute(text('''
        SELECT id, name, url, description, short_description
        FROM conferences
        ORDER BY created_at DESC
    '''))
    
    conferences = result.fetchall()
    print(f"📊 Testing improved filtering on {len(conferences)} conferences")
    
    # Test URL filtering
    would_be_excluded_by_url = []
    for conf in conferences:
        id, name, url, description, short_description = conf
        url_lower = (url or '').lower()
        
        # Check if URL contains exclude patterns
        should_exclude = any(pattern in url_lower for pattern in exclude_patterns)
        
        if should_exclude:
            would_be_excluded_by_url.append((id, name, url))
    
    print(f"🔍 URL filtering would exclude: {len(would_be_excluded_by_url)} conferences")
    
    # Show examples
    if would_be_excluded_by_url:
        print("\n🔍 Examples that would be excluded by URL filtering:")
        for i, (id, name, url) in enumerate(would_be_excluded_by_url[:10]):
            print(f"  {i+1:2d}. {name[:50]}...")
            print(f"      → {url}")
            print()
    
    # Test content filtering
    non_conference_indicators = [
        'blog', 'article', 'guide', 'tutorial', 'course', 'lesson',
        'subscription', 'newsletter', 'sign up', 'create account',
        'login', 'register', 'form', 'download', 'resource',
        'use case', 'case study', 'pricing', 'demo', 'trial',
        'business plan', 'platform', 'software', 'solution',
        'product launch', 'sales kickoff', 'employer branding',
        'discussion', 'forum', 'community', 'support', 'help',
        'documentation', 'api', 'integration', 'migration',
        'certification', 'training', 'learning',
        'collection of blogs', 'blog features', 'explore how',
        'no description available', 'user profile', 'user community',
        'create your free account', 'step into a new era',
        'maximize the full value', 'build resilience',
        'streamline workflows', 'boost efficiency',
        # NEW patterns
        'status page', 'system status', 'operational status',
        'incident notifications', 'service status',
        'ticketing tools', 'event ticketing', 'ticketing platform',
        'food and drink event', 'event industry tools',
        'splunk blogs', 'blog subscription', 'industries blogs',
        'security blog', 'author blog', 'community profile',
        'viewprofilepage', 'user-id',
        'polls and surveys', 'hybrid webinars', 'virtual event tools',
        'webinar platform', 'event platform', 'meeting platform',
        'learning platform', 'business provides', 'software makes',
        'platform for', 'tools to help', 'resources to help',
        'explore a collection of', 'subscribe to', 'get help for'
    ]
    
    # Required conference indicators
    conference_indicators = [
        'conference', 'summit', 'symposium', 'expo', 'convention',
        'gathering', 'festival', 'event', 'workshop', 'meetup',
        'congress', 'forum', 'seminar', 'hackathon', 'bootcamp',
        'speakers', 'keynote', 'sessions', 'presentations',
        'networking', 'attendees', 'registration', 'agenda'
    ]
    
    would_be_excluded_by_content = []
    for conf in conferences:
        id, name, url, description, short_description = conf
        
        name_lower = (name or '').lower()
        desc_lower = (description or '').lower()
        short_desc_lower = (short_description or '').lower()
        
        all_text = f"{name_lower} {desc_lower} {short_desc_lower}"
        
        # Check if it has obvious non-conference indicators
        has_non_conference = any(indicator in all_text for indicator in non_conference_indicators)
        
        # Check if it has conference indicators
        has_conference = any(indicator in all_text for indicator in conference_indicators)
        
        # Special checks
        is_blog = 'blog' in name_lower or 'blog' in desc_lower
        is_signup = any(x in all_text for x in ['sign up', 'create account', 'registration form'])
        is_user_profile = 'user profile' in all_text or 'viewprofilepage' in url
        is_company_page = any(x in all_text for x in ['company', 'business solution', 'platform'])
        
        # Decision logic (same as in our filtering)
        should_exclude = False
        
        if is_blog or is_signup or is_user_profile:
            should_exclude = True
        elif has_non_conference and not has_conference:
            should_exclude = True
        elif not has_conference and is_company_page:
            should_exclude = True
        elif any(x in all_text for x in [
            'our software makes it simple',
            'explore a collection of',
            'subscribe to', 'get help for',
            'resources to help you find',
            'learning platform for', 'provides a learning platform',
            'business provides', 'for business provides',
            'catering to all skill levels', 'data and ai needs'
        ]):
            should_exclude = True
        elif any(x in url.lower() for x in [
            '/business', '/platform', '/software', '/product'
        ]) and not has_conference:
            should_exclude = True
        
        if should_exclude:
            would_be_excluded_by_content.append((id, name, url, all_text[:100]))
    
    print(f"📝 Content filtering would exclude: {len(would_be_excluded_by_content)} conferences")
    
    # Show examples
    if would_be_excluded_by_content:
        print("\n📝 Examples that would be excluded by content filtering:")
        for i, (id, name, url, text_sample) in enumerate(would_be_excluded_by_content[:5]):
            print(f"  {i+1:2d}. {name[:50]}...")
            print(f"      → {url}")
            print(f"      📝 {text_sample}...")
            print()
    
    # Calculate total that would be excluded
    url_excluded_ids = {conf[0] for conf in would_be_excluded_by_url}
    content_excluded_ids = {conf[0] for conf in would_be_excluded_by_content}
    total_excluded_ids = url_excluded_ids | content_excluded_ids
    
    print(f"\n📊 Summary:")
    print(f"   Total conferences: {len(conferences)}")
    print(f"   Would be excluded by URL filtering: {len(url_excluded_ids)}")
    print(f"   Would be excluded by content filtering: {len(content_excluded_ids)}")
    print(f"   Total unique exclusions: {len(total_excluded_ids)}")
    print(f"   Would remain after filtering: {len(conferences) - len(total_excluded_ids)}")
    print(f"   Filtering effectiveness: {len(total_excluded_ids)/len(conferences)*100:.1f}%")
    
    session.close()

if __name__ == "__main__":
    test_improved_url_filtering() 