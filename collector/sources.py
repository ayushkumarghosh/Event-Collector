from dataclasses import dataclass


@dataclass
class FeedSource:
    name: str
    url: str
    category: str
    feed_type: str = "rss"
    priority: int = 5


SOURCES = [
    # --- State (Government / Political) ---
    FeedSource("The Hindu National", "https://www.thehindu.com/news/national/feeder/default.rss", "state", priority=8),
    FeedSource("Indian Express India", "https://indianexpress.com/section/india/feed/", "state", priority=8),
    FeedSource("News18 India", "https://www.news18.com/rss/india.xml", "state", priority=7),
    FeedSource("Tribune India", "https://publish.tribuneindia.com/newscategory/nation/feed/", "state", priority=6),
    FeedSource("India TV News India", "https://www.indiatvnews.com/rssnews/topstory-india.xml", "state", priority=6),

    # --- Situation (Disasters, Sports, Business, Trends, Entertainment — ongoing/upcoming) ---
    FeedSource("NDTV India", "https://feeds.feedburner.com/ndtvnews-india-news", "situation", priority=9),
    FeedSource("The Hindu", "https://www.thehindu.com/feeder/default.rss", "situation", priority=7),
    FeedSource("News18 India Situation", "https://www.news18.com/rss/india.xml", "situation", priority=7),
    FeedSource("India TV News Top", "https://www.indiatvnews.com/rssnews/topstory.xml", "situation", priority=6),
    FeedSource("ESPNcricinfo India", "https://www.espncricinfo.com/rss/content/story/feeds/0.xml", "situation", priority=9),
    FeedSource("Economic Times", "https://economictimes.indiatimes.com/rssfeedstopstories.cms", "situation", priority=7),
    FeedSource("News18 Sports", "https://www.news18.com/rss/sports.xml", "situation", priority=8),
    FeedSource("Indian Express Cricket", "https://indianexpress.com/section/sports/cricket/feed/", "situation", priority=8),
    FeedSource("The Hindu Sport", "https://www.thehindu.com/sport/feeder/default.rss", "situation", priority=7),
    FeedSource("Hindustan Times Sports", "https://www.hindustantimes.com/feeds/rss/sports/rssfeed.xml", "situation", priority=7),
    FeedSource("Livemint Sports", "https://www.livemint.com/rss/sports", "situation", priority=6),
    FeedSource("Tribune Sports", "https://publish.tribuneindia.com/newscategory/sports/feed/", "situation", priority=6),
    FeedSource("India TV Sports", "https://www.indiatvnews.com/rssnews/topstory-sports.xml", "situation", priority=5),
    FeedSource("India Today Trending", "https://www.indiatoday.in/rss/home", "situation", priority=8),
    FeedSource("NDTV India Trends", "https://feeds.feedburner.com/ndtvnews-india-news", "situation", priority=7),
    FeedSource("HT India Trends", "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml", "situation", priority=7),
    FeedSource("India TV Trending", "https://www.indiatvnews.com/rssnews/topstory-trending.xml", "situation", priority=6),
    FeedSource("Bollywood Hungama", "https://www.bollywoodhungama.com/feed/", "situation", priority=8),
    FeedSource("News18 Entertainment", "https://www.news18.com/rss/entertainment.xml", "situation", priority=8),
    FeedSource("Indian Express Entertainment", "https://indianexpress.com/section/entertainment/feed/", "situation", priority=7),
    FeedSource("Hindustan Times Entertainment", "https://www.hindustantimes.com/feeds/rss/entertainment/rssfeed.xml", "situation", priority=7),
    FeedSource("The Hindu Entertainment", "https://www.thehindu.com/entertainment/feeder/default.rss", "situation", priority=6),
    FeedSource("India TV Entertainment", "https://www.indiatvnews.com/rssnews/topstory-entertainment.xml", "situation", priority=5),
]


def get_sources(category_filter: str | None = None) -> list[FeedSource]:
    if category_filter:
        return [s for s in SOURCES if s.category == category_filter]
    return list(SOURCES)
