"""Journal feeds to scan. `weight` is a rough prior for how often a journal
publishes broadly significant work; the AI ranking step makes the final call."""

SOURCES = [
    # Multidisciplinary flagships
    {"journal": "Nature", "url": "https://www.nature.com/nature.rss", "weight": 1.0},
    {"journal": "Science", "url": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science", "weight": 1.0},
    {"journal": "Cell", "url": "https://www.cell.com/cell/inpress.rss", "weight": 0.95},
    {"journal": "PNAS", "url": "https://www.pnas.org/action/showFeed?type=etoc&feed=rss&jc=pnas", "weight": 0.8},
    {"journal": "Nature Communications", "url": "https://www.nature.com/ncomms.rss", "weight": 0.7},
    {"journal": "Science Advances", "url": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=sciadv", "weight": 0.7},
    # Medicine
    {"journal": "The New England Journal of Medicine", "url": "https://www.nejm.org/action/showFeed?type=etoc&feed=rss&jc=nejm", "weight": 0.95},
    {"journal": "The Lancet", "url": "https://www.thelancet.com/rssfeed/lancet_online.xml", "weight": 0.9},
    {"journal": "Nature Medicine", "url": "https://www.nature.com/nm.rss", "weight": 0.85},
    # Field journals
    {"journal": "Nature Physics", "url": "https://www.nature.com/nphys.rss", "weight": 0.8},
    {"journal": "Nature Astronomy", "url": "https://www.nature.com/natastron.rss", "weight": 0.8},
    {"journal": "Nature Climate Change", "url": "https://www.nature.com/nclimate.rss", "weight": 0.8},
    {"journal": "Nature Neuroscience", "url": "https://www.nature.com/neuro.rss", "weight": 0.8},
    {"journal": "Nature Biotechnology", "url": "https://www.nature.com/nbt.rss", "weight": 0.8},
    {"journal": "Physical Review Letters", "url": "https://feeds.aps.org/rss/recent/prl.xml", "weight": 0.8},
    {"journal": "PLOS Biology", "url": "https://journals.plos.org/plosbiology/feed/atom", "weight": 0.65},
    {"journal": "eLife", "url": "https://elifesciences.org/rss/recent.xml", "weight": 0.65},
]

# Feed items whose titles start with these are usually not original research.
NON_RESEARCH_PREFIXES = (
    "author correction", "publisher correction", "correction", "erratum", "retraction",
    "editorial", "news", "news & views", "news and views", "comment", "correspondence",
    "letter", "perspective", "book review", "obituary", "career", "daily briefing",
    "podcast", "audio", "video", "in brief", "this week", "editor's note", "editors' note",
    "expression of concern", "reply to", "matters arising", "q&a", "where i work",
)
