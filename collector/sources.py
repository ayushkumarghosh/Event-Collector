from dataclasses import dataclass


@dataclass
class FeedSource:
    name: str
    url: str
    category: str
    feed_type: str = "rss"
    priority: int = 5


SOURCES = [
    # --- Government ---
    FeedSource("The Hindu National", "https://www.thehindu.com/news/national/feeder/default.rss", "govt", priority=8),
    FeedSource("Indian Express India", "https://indianexpress.com/section/india/feed/", "govt", priority=8),
    FeedSource("News18 India", "https://www.news18.com/rss/india.xml", "govt", priority=7),
    FeedSource("Tribune India", "https://publish.tribuneindia.com/newscategory/nation/feed/", "govt", priority=6),
    FeedSource("India TV News India", "https://www.indiatvnews.com/rssnews/topstory-india.xml", "govt", priority=6),

    # --- Disaster ---
    FeedSource("NDTV India", "https://feeds.feedburner.com/ndtvnews-india-news", "disaster", priority=9),
    FeedSource("The Hindu", "https://www.thehindu.com/feeder/default.rss", "disaster", priority=7),
    FeedSource("News18 India Disaster", "https://www.news18.com/rss/india.xml", "disaster", priority=7),
    FeedSource("India TV News Top", "https://www.indiatvnews.com/rssnews/topstory.xml", "disaster", priority=6),

    # --- Sports ---
    FeedSource("ESPNcricinfo India", "https://www.espncricinfo.com/rss/content/story/feeds/0.xml", "sports", priority=9),
    FeedSource("Economic Times", "https://economictimes.indiatimes.com/rssfeedstopstories.cms", "sports", priority=7),
    FeedSource("News18 Sports", "https://www.news18.com/rss/sports.xml", "sports", priority=8),
    FeedSource("Indian Express Cricket", "https://indianexpress.com/section/sports/cricket/feed/", "sports", priority=8),
    FeedSource("The Hindu Sport", "https://www.thehindu.com/sport/feeder/default.rss", "sports", priority=7),
    FeedSource("Hindustan Times Sports", "https://www.hindustantimes.com/feeds/rss/sports/rssfeed.xml", "sports", priority=7),
    FeedSource("Livemint Sports", "https://www.livemint.com/rss/sports", "sports", priority=6),
    FeedSource("Tribune Sports", "https://publish.tribuneindia.com/newscategory/sports/feed/", "sports", priority=6),
    FeedSource("India TV Sports", "https://www.indiatvnews.com/rssnews/topstory-sports.xml", "sports", priority=5),

    # --- Trends ---
    FeedSource("India Today Trending", "https://www.indiatoday.in/rss/home", "trends", priority=8),
    FeedSource("NDTV India Trends", "https://feeds.feedburner.com/ndtvnews-india-news", "trends", priority=7),
    FeedSource("HT India Trends", "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml", "trends", priority=7),
    FeedSource("India TV Trending", "https://www.indiatvnews.com/rssnews/topstory-trending.xml", "trends", priority=6),

    # --- Entertainment ---
    FeedSource("Bollywood Hungama", "https://www.bollywoodhungama.com/feed/", "entertainment", priority=8),
    FeedSource("News18 Entertainment", "https://www.news18.com/rss/entertainment.xml", "entertainment", priority=8),
    FeedSource("Indian Express Entertainment", "https://indianexpress.com/section/entertainment/feed/", "entertainment", priority=7),
    FeedSource("Hindustan Times Entertainment", "https://www.hindustantimes.com/feeds/rss/entertainment/rssfeed.xml", "entertainment", priority=7),
    FeedSource("The Hindu Entertainment", "https://www.thehindu.com/entertainment/feeder/default.rss", "entertainment", priority=6),
    FeedSource("India TV Entertainment", "https://www.indiatvnews.com/rssnews/topstory-entertainment.xml", "entertainment", priority=5),
]


def get_sources(category_filter: str | None = None) -> list[FeedSource]:
    if category_filter:
        return [s for s in SOURCES if s.category == category_filter]
    return list(SOURCES)
