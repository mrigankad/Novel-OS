"""Research swarm: browser agents that search, read and cite.

browser.fetch(url) -> Page      polite fetching (robots.txt, 10s, 2 MB, 1 per domain)
search.search(query, n) -> hits DuckDuckGo HTML by default, Brave / Tavily with keys
swarm.start(...)                orchestrates sub-queries, parallel workers, synthesis
"""
