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
    # Medicine and health
    {"journal": "The New England Journal of Medicine", "url": "https://www.nejm.org/action/showFeed?type=etoc&feed=rss&jc=nejm", "weight": 0.95},
    {"journal": "The Lancet", "url": "https://www.thelancet.com/rssfeed/lancet_online.xml", "weight": 0.9},
    {"journal": "JAMA", "url": "https://jamanetwork.com/rss/site_3/67.xml", "weight": 0.9},
    {"journal": "The BMJ", "url": "https://www.bmj.com/rss/research.xml", "weight": 0.85},
    {"journal": "Nature Medicine", "url": "https://www.nature.com/nm.rss", "weight": 0.85},
    {"journal": "Science Translational Medicine", "url": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=stm", "weight": 0.8},
    {"journal": "PLOS Medicine", "url": "https://journals.plos.org/plosmedicine/feed/atom", "weight": 0.65},
    {"journal": "Nature Human Behaviour", "url": "https://www.nature.com/nathumbehav.rss", "weight": 0.8},
    # Physical sciences
    {"journal": "Physical Review Letters", "url": "https://feeds.aps.org/rss/recent/prl.xml", "weight": 0.8},
    {"journal": "Nature Physics", "url": "https://www.nature.com/nphys.rss", "weight": 0.8},
    {"journal": "Nature Astronomy", "url": "https://www.nature.com/natastron.rss", "weight": 0.8},
    {"journal": "Nature Chemistry", "url": "https://www.nature.com/nchem.rss", "weight": 0.8},
    {"journal": "Nature Materials", "url": "https://www.nature.com/nmat.rss", "weight": 0.8},
    {"journal": "Nature Nanotechnology", "url": "https://www.nature.com/nnano.rss", "weight": 0.8},
    # Computing and engineering
    {"journal": "Nature Machine Intelligence", "url": "https://www.nature.com/natmachintell.rss", "weight": 0.75},
    {"journal": "Nature Computational Science", "url": "https://www.nature.com/natcomputsci.rss", "weight": 0.7},
    {"journal": "Nature Electronics", "url": "https://www.nature.com/natelectron.rss", "weight": 0.75},
    {"journal": "Nature Energy", "url": "https://www.nature.com/nenergy.rss", "weight": 0.8},
    {"journal": "Science Robotics", "url": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=scirobotics", "weight": 0.75},
    {"journal": "Nature Biotechnology", "url": "https://www.nature.com/nbt.rss", "weight": 0.8},
    # Life sciences
    {"journal": "Nature Neuroscience", "url": "https://www.nature.com/neuro.rss", "weight": 0.8},
    {"journal": "Nature Genetics", "url": "https://www.nature.com/ng.rss", "weight": 0.8},
    {"journal": "Nature Cell Biology", "url": "https://www.nature.com/ncb.rss", "weight": 0.75},
    {"journal": "Nature Microbiology", "url": "https://www.nature.com/nmicrobiol.rss", "weight": 0.75},
    {"journal": "Nature Ecology & Evolution", "url": "https://www.nature.com/natecolevol.rss", "weight": 0.75},
    {"journal": "Nature Plants", "url": "https://www.nature.com/nplants.rss", "weight": 0.7},
    {"journal": "PLOS Biology", "url": "https://journals.plos.org/plosbiology/feed/atom", "weight": 0.65},
    {"journal": "eLife", "url": "https://elifesciences.org/rss/recent.xml", "weight": 0.65},
    # Earth, environment, food and society
    {"journal": "Nature Climate Change", "url": "https://www.nature.com/nclimate.rss", "weight": 0.8},
    {"journal": "Nature Geoscience", "url": "https://www.nature.com/ngeo.rss", "weight": 0.8},
    {"journal": "Nature Sustainability", "url": "https://www.nature.com/natsustain.rss", "weight": 0.75},
    {"journal": "Nature Water", "url": "https://www.nature.com/natwater.rss", "weight": 0.7},
    {"journal": "Nature Food", "url": "https://www.nature.com/natfood.rss", "weight": 0.7},
    # Preprints (not yet peer reviewed): the main home of new maths, CS, statistics and economics.
    # Capped so they don't crowd out journals.
    {"journal": "arXiv (Mathematics)", "url": "https://rss.arxiv.org/rss/math", "weight": 0.45, "preprint": True, "max_items": 40},
    {"journal": "arXiv (Computer Science)", "url": "https://rss.arxiv.org/rss/cs.AI+cs.LG+cs.CR+cs.CL", "weight": 0.45, "preprint": True, "max_items": 40},
    {"journal": "arXiv (Statistics)", "url": "https://rss.arxiv.org/rss/stat.ML+stat.ME+stat.TH", "weight": 0.45, "preprint": True, "max_items": 20},
    {"journal": "arXiv (Economics & Finance)", "url": "https://rss.arxiv.org/rss/econ+q-fin", "weight": 0.45, "preprint": True, "max_items": 20},
    {"journal": "arXiv (Robotics & Control)", "url": "https://rss.arxiv.org/rss/cs.RO+eess.SY", "weight": 0.45, "preprint": True, "max_items": 20},
]

DEFAULT_MAX_ITEMS = 40   # newest items kept per feed

# Feed items whose titles start with these are usually not original research.
NON_RESEARCH_PREFIXES = (
    "author correction", "publisher correction", "correction", "erratum", "retraction",
    "editorial", "news", "news & views", "news and views", "comment", "correspondence",
    "letter", "perspective", "book review", "obituary", "career", "daily briefing",
    "podcast", "audio", "video", "in brief", "this week", "editor's note", "editors' note",
    "expression of concern", "reply to", "matters arising", "q&a", "where i work",
)
