"""Mode-specific H3 guides adapted from MiniMax's writing skill and the local Ref2AV example."""

BASE_FIELDS = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
REF_FIELDS = ("subject_definitions", "summary", "retention_analysis", "detailed_description", *BASE_FIELDS[1:])
REF_TASKS = ("reference generation", "keyframe completion", "video continuation", "video editing", "audio reuse", "audio reference")

ALIGNMENTS = {
    "i2va": "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.",
    "flf2va": "How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.",
    "l2va": "How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.",
}

PRESERVE_BRIEF = """Treat the original brief as authoritative for plot, cast, required actions, duration, dialogue and constraints. Preserve specified speech, lyrics and visible text verbatim in their original language. Treat labeled dialogue examples as inspiration. Respect requests for silence, music or a particular shot count. Use the specified duration, or 15 seconds when omitted. Fill only gaps needed to make the story filmable."""

STAGING = """Fit the required lines, physical actions and final reaction into the runtime. Choose a framing that can show the action: a hand insert shows contact with a prop; a wider composition can also show the actor's expression. Keep the fewest shots that convey the brief. Carry prop ownership, position and state through each cut.
For an object speaking alone, locate the voice at its physical source and distinguish its resonance from the human voice. When composition permits, hold on the object with human mouths and reflections out of frame until the line finishes. In a required shared frame, show the silent listener reacting with eyes or posture and relaxed, closed lips. A rigid object keeps its shape unless the brief calls for articulation. Respect requested overlaps, continuous shots and frame anchors."""

_TIMELINE = """Write the shot narrative in playback order. Number every cut as a new shot. [Shot 1] has no timestamp; each later shot begins like “[Shot 2] At 00:04.200, the camera cuts to …” with a strictly increasing time inside the runtime. A pan or push within one take keeps the same shot number. Establish blocking and screen direction, then describe observable changes in action, lighting and synchronized sound. Use camera speed or amplitude when it changes what the viewer sees."""

_AUDIO = """Assign (S1), (S2), etc. in order of first vocal event, independently of visual subject numbers. For each line place the speaker's name or reference label, its stable ID and delivery immediately before <d>[language name] words</d>. Keep only the language and verbatim utterance inside the tag. Separate successive speakers with a listening beat when time permits. For voiceover use “says in an off-screen voiceover” and, immediately after the line, describe the visible speaker's closed lips. Mark both sides of a line spanning a cut with <scenetrans> and describe the continuous audio. Use <cutoff> for speech cut short by the ending. Quote visible text with double quotes.
Put dialogue, singing and in-scene music in the shot narrative. Use overall_soundscape for ambience, physical sounds and nonverbal reactions. Use N/A for explicitly complete silence. Use non_diegetic_music for audience-only music, specifying instruments, tempo and dynamics where requested or useful. Use N/A when there is no score."""

_REF = """In subject_definitions give each independently tracked reference one line. A <Subject N> denotes content drawn from a supplied or user-identified asset. Name newly generated people, props and settings in ordinary prose, even if they speak. Cite appearance-only pictures inside the subject definition; give a picture its own definition and retention line only for a frame, composition or storyboard role. Describe features supported by the asset or brief. For a downstream asset you cannot see, bind the requested role without guessing its appearance. Use <Video N> for whole-video structure, edits or continuation. Create <Audio N> only for sound actually referenced or reused.
Open summary with the applicable task types (reference generation, keyframe completion, video editing, video continuation, audio reuse, audio reference) in brackets, joined by ' + '. For video editing, begin the sentence with “The target video is an edited version of <Video 1>.” In retention_analysis give one line per standalone definition. For example: <Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - the referenced facial features and hairstyle persist. List actual shot appearances. Assess only the defined role: new actions, angles or surroundings can preserve identity fully. Use partially_preserved for changes to defined features, attribute_transfer for features applied to another subject, and weak_reference for broad resemblance. For audio choose fully_copy for a complete unchanged final track, partially_copy for excerpts or remixed layers, reference for guidance, or weak_reference for broad similarity.
Begin detailed_description with one or two English sentences establishing visual style before [Shot 1]. At each reference's first visible or audible use, place its label beside the corresponding action or sound. Carry the same mapping across shots. A referenced speaker uses <Subject N> (Sx); an invented speaker uses its ordinary name and (Sx). For generation, aim for roughly 350–500 English words when useful; prioritize the spoken timeline and visible detail. Mention referenced audio in the section for its audible layer."""

MODE_GUIDES = {
    "1ref2va": """Identify what the one supplied asset contributes. For a single character image, map <Picture 1> to the relevant <Subject 1> identity. Preserve face, hair, age, body proportions and any requested outfit. A reference with multiple visible elements may support separately defined subjects only where the brief uses them. Infer the role from the brief: an appearance reference supplies identity, a style sample supplies visual treatment, and only a designated frame anchor fixes composition.""",
    "2ref2va": """Map both assets to their roles before writing the scene. For two distinct character images, bind <Picture 1> to <Subject 1> and <Picture 2> to <Subject 2>. Keep identities distinct during movement and reverse angles. Establish each character’s position and eyeline in the target scene. Combine assets in one definition when the brief establishes a shared identity or complementary attributes. Identify each speaker by vocal order, even when <Subject 2> speaks first. Appearance references do not establish target frames unless the brief assigns that use.""",
    "Nref2va": """Map each reference to a defined role and use it in the relevant shots. Maintain separate Picture, Video, Audio and Subject numbering. Several assets can contribute different features to one subject, and one asset can support multiple subjects. Track each reference through costume, movement, style, linked props or audio as assigned. Keep the story focused and avoid inventing unused references or changing their roles.""",
    "i2va": """Open on the exact composition, pose and object positions in Picture 1. Establish the image's style within [Shot 1], then give the subjects a plausible onset of motion that leads to a visible result. Carry its wardrobe, props, lighting and spatial anchors forward. A single continuous shot works when the action needs no cut.""",
    "flf2va": """Start with Picture 1 and end in the exact composition and state in Picture 2. Describe concrete intermediate changes in pose, object state, lighting and composition so the ending follows causally from the opening. Default to one continuous shot. Use cuts only if explicitly requested. Resolve the alignment line with the actual last shot index and the requested runtime.""",
    "l2va": """Treat Picture 1 as the ending. Infer a plausible preceding composition and show the physical progression that brings the subjects, props, framing and light into the supplied final state. Land on Picture 1 in the actual last shot at the requested runtime. Preserve what the ending image establishes about identity and geography.""",
    "t2va": """Build the whole audiovisual timeline from the text. Establish the visual style, initial composition, subject identities, setting and relevant props in [Shot 1]. Show the requested action and reactions with spatial continuity. Begin with the three core fields. Omit picture alignment, reference definitions and invented reference labels.""",
}


def writing_system_prompt(mode, fields):
    parts = [
        f"Write one ready-to-use MiniMax H3 prompt for {mode}. Use the shooting plan for staging and the original brief to check facts and exact lines. Return only the finished prompt.",
        PRESERVE_BRIEF,
        MODE_GUIDES[mode],
        STAGING,
        _TIMELINE,
        _AUDIO,
    ]
    if fields == REF_FIELDS:
        parts.append(_REF)
    else:
        parts.append("Open integrated_multimodal_description with [Shot 1], then establish the visual style and opening composition.")
    if mode in ALIGNMENTS:
        parts.append(f"Begin with this alignment line, followed by a blank line. Replace N with the last shot index and S.SS with the runtime to two decimal places wherever those placeholders occur.\n{ALIGNMENTS[mode]}")
    parts.append("Write these exact field names in order. Use plain text without a title or Markdown fence.\n" + "\n".join(field + ":" for field in fields))
    return "\n\n".join(parts)
