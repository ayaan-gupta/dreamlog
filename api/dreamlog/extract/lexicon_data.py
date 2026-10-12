"""The word lists behind the offline extractor.

Lemmas are singular and lower case. A word appears under one kind only. This is
a list of things a dream can contain, not a list of what they mean: nothing
here maps one word to another, and merging "ocean" into "water" is left to the
embedding model in ``canonical.py``.
"""

from __future__ import annotations

from .base import Kind, Mood

LEXICON: dict[Kind, str] = {
    "place": """
        house home room kitchen bedroom bathroom attic basement cellar corridor hallway hall staircase stairs stairwell
        elevator lift escalator roof garden yard backyard street road path alley bridge tunnel city town village school
        classroom university college library office hospital church cathedral temple hotel motel airport station
        platform supermarket shop store mall market restaurant cafe bar pub theatre theater cinema stage museum gallery
        park playground forest woods jungle field meadow hillside hill mountain valley cave cliff desert island beach
        shore coast harbour harbor port pier lighthouse tower castle palace prison cemetery graveyard farm barn factory
        warehouse garage stadium pitch gym pool apartment building cabin cottage hut tent camp maze labyrinth
        laboratory courtroom zoo aquarium circus windmill gate exit entrance landing aisle carriage chimney
        swimming_pool train_station bus_stop car_park parking_lot living_room dining_room waiting_room high_school
        shopping_mall post_office
    """,
    "person": """
        mother father mom mum dad parent brother sister sibling grandmother grandfather grandma grandpa grandparent
        aunt uncle cousin son daughter child kid baby infant toddler boy girl man woman husband wife partner boyfriend
        girlfriend friend stranger neighbour neighbor teacher professor student classmate boss colleague coworker
        doctor nurse dentist surgeon policeman officer guard soldier thief burglar killer murderer ghost witch wizard
        king queen prince princess priest nun driver pilot conductor waiter shopkeeper crowd audience figure twin
        invigilator examiner judge lawyer actor singer clown teenager giant angel demon devil alien zombie vampire
        captain sailor farmer hunter
    """,
    "animal": """
        dog puppy cat kitten wolf fox bear lion tiger horse cow pig sheep goat deer rabbit mouse rat bat bird crow
        raven owl eagle hawk pigeon dove swan duck chicken fish shark whale dolphin octopus jellyfish crab snake
        serpent lizard crocodile alligator frog toad turtle spider insect bee wasp ant butterfly moth worm dragon
        elephant monkey ape gorilla giraffe zebra squirrel hedgehog seal penguin peacock beetle cockroach swarm
        animal creature monster beast
    """,
    "nature": """
        water ocean sea lake river pond stream waterfall wave tide flood rain storm thunder lightning snow ice hail
        fog mist cloud wind tornado hurricane fire flame smoke ash sun moon star sky planet comet sunrise sunset
        darkness light shadow rainbow tree branch root leaf flower rose sunflower grass vine moss mushroom seed fruit
        apple sand mud dust rock stone pebble crystal earthquake volcano lava hole pit abyss
    """,
    "object": """
        door window key lock keyhole wall floor ceiling mirror reflection clock watch phone telephone computer laptop
        screen television radio camera photograph photo picture painting book notebook diary letter envelope page
        paper pen pencil map ticket passport money coin wallet purse bag backpack suitcase luggage box chest drawer
        cupboard wardrobe closet shelf bookcase table desk chair sofa couch bed pillow blanket curtain carpet rug lamp
        candle lantern torch knife sword gun rope chain string thread needle scissors hammer ladder umbrella hat coat
        jacket dress shirt shoe boot glove ring necklace mask costume uniform clothes car bus truck van taxi train
        tram bicycle bike motorcycle boat ship raft plane airplane helicopter rocket balloon kite wheel engine brake
        seat piano guitar violin drum bell toy doll ball puzzle cake bread tea coffee wine milk egg cup glass bottle
        plate bowl kettle pot oven fridge sink bath bathtub shower toilet tap hose bucket statue sculpture coffin grave
        tombstone sarcophagus cross flag sign button switch lever machine robot wire cable net cage trap fence feather
        shell skull web nest tin folder headlight velvet pocket footstep
        diving_board hot_air_balloon washing_machine
    """,
    "body": """
        tooth hand finger arm eye mouth tongue hair face blood bone skin wing tail voice
    """,
    "event": """
        exam test wedding funeral party meeting presentation interview play concert race war fight accident crash
        lesson lecture ceremony festival
    """,
}

# Plurals that the suffix rules get wrong.
IRREGULAR: dict[str, str] = {
    "teeth": "tooth", "feet": "foot", "children": "child", "men": "man", "women": "woman", "mice": "mouse",
    "geese": "goose", "wolves": "wolf", "leaves": "leaf", "knives": "knife", "shelves": "shelf", "thieves": "thief",
    "babies": "baby", "cities": "city", "ladies": "lady", "parties": "party", "bodies": "body",
}  # fmt: skip


def _words(block: str) -> frozenset[str]:
    return frozenset(block.split())


# Words that never head a symbol, however they are introduced.
STOPWORDS = _words("""
    a an the and or but so if then than that this these those there here it its i me my mine we us our ours you your
    he him his she her hers they them their theirs who whom whose which what where when why how all any both each few
    more most other some such no nor not only own same too very just also still yet even ever never always often
    of in on at by for with about against between into through during before after above below to from up down out
    off over under again further once is am are was were be been being have has had having do does did doing would
    could should can will shall may might must as because until while like though although whether nobody everybody
    somebody anyone everyone someone nothing something everything anything myself yourself himself herself itself
    ourselves themselves
""")

DETERMINERS = _words("a an the my our his her their its this that these those some every each another one two three")

# Common verbs in past or base form. A run of words after a determiner stops here.
VERBS = _words("""
    went came saw said took gave fell ran stood sat held kept knew felt turned got made found left told heard thought
    began became brought caught drove flew grew hid led lost met paid put read rode rose sang sent shut slept spoke
    spent swam threw woke wore wrote go come see say take give fall run stand sit hold keep know feel turn get make
    find leave tell hear think look looked seem seemed want wanted try tried start started stop stopped open opened
    close closed walk walked climb climbed reach reached pull pulled push pushed wave waved point pointed hand handed
    cut slip slipped pass passed float floated steer steered jump jumped wait waited sound sounded cover covered
""")

# Adjectives and vague nouns that the determiner pattern would otherwise pick up.
NOT_SYMBOLS = _words("""
    way thing things time kind sort lot bit rest middle side top bottom front back end part place moment feeling mood
    sense order name names word words reason idea fact point number hour minute second day week month year night
    morning evening afternoon dream nightmare sleep distance direction sound noise silence air world life death
    whole half piece pieces row rows curve curves bend bends corner step steps times miles metres meters seconds
    months years hours language lines note notes people person someone others one ones
    small big large huge tiny little long short tall high low old young new good bad wrong right same different
    black white grey gray red blue green yellow gold silver brown pink purple orange dark bright warm cold hot wet
    dry heavy light slow fast loud quiet empty full open closed last first next only own enormous strange
    clear flat deep thick thin tight spiral marble brass wooden maths animal football goal apple work
    childhood security strong funny happy scary angry sorry lucky ready later ago away ahead early late
""")

# Body words that are almost always the dreamer's own and almost never the point.
BODY_NOISE = _words("leg heart back neck chest stomach breath head foot shoulder knee")


def _cues(block: str, weak: str = "") -> dict[str, float]:
    return dict.fromkeys(block.split(), 1.0) | dict.fromkeys(weak.split(), 0.5)


# Cue words for mood tags. A weak cue counts half.
MOOD_CUES: dict[Mood, dict[str, float]] = {
    "calm": _cues("calm peaceful quiet content safe relaxed serene relieved relief comfortable soothing", "still slowly gently"),
    "joyful": _cues("happy joy joyful laughing laughed laugh delighted wonderful fun funny excited glad smiling smiled playful cheerful"),
    "anxious": _cues(
        "anxious worried worry nervous panic panicked stressed embarrassed ashamed guilty stuck trapped dread uneasy tense stupid sick losing",
        "lost late",
    ),
    "fearful": _cues(
        "afraid scared terrified frightened frightening fear horror terror scream screaming pounding hide hid threatening "
        "danger dangerous hunting chasing"
    ),
    "sad": _cues("sad crying cried tears grief lonely alone missing died dead mourning sorrow heartbroken"),
    "nostalgic": _cues("childhood homesick homesickness younger memory nostalgic familiar", "again remember remembered"),
    "awed": _cues("awe vast beautiful wonder amazing magical glowing infinite endless majestic", "huge enormous"),
    "confused": _cues("confused confusing strange odd weird puzzled wrong impossible bizarre surreal unfamiliar sideways backwards"),
    "angry": _cues("angry furious rage shouting shouted yelled annoyed fighting hate argued argument"),
    "tender": _cues("love loved fond hug hugged kiss kissed tender caring grateful embrace smiled"),
}

NEGATORS = _words("not no never without hardly nobody")
