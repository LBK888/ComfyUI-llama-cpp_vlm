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

_TIMELINE = """Write descriptions in English, preserving original speech, lyrics and on-screen text. Begin with [Shot 1] and no timestamp. Start any later shot with an increasing cut time inside the runtime. Use the form “[Shot 2] At 00:04.200, …”. Use a hook, a causal development and a readable final state when the story permits. Default to three shots for a micro-story and keep it to four or fewer unless the brief specifies more. Apply any tighter constraints from the selected mode. Give each cut a purpose. Prefer reframing within a shot to changing shots merely for distance.
Describe observable framing, blocking, lighting, gaze, actions, prop states and synchronized sounds. Show each required action from preparation through execution, readable result and reaction. Keep identities, eyelines, screen direction, props, lighting and geography continuous. Name a camera move and give speed or amplitude when it matters. Keep faces readable during speech."""

_AUDIO = """Assign (S1), (S2), etc. in order of first vocal event and keep them independent of visual subject numbers. Write dialogue and lyrics inside <d>[language name] words</d>. Keep the actor, delivery and quote delimiters outside the tag. For voiceover by a visible character, identify it as off-screen and keep that character's lips closed. Use <scenetrans> when speech carries across a cut, and <cutoff> for speech cut short at the ending. Quote visible text with double quotes.
Put dialogue, singing and in-scene music in the shot narrative. Use overall_soundscape for ambience, physical sounds and nonverbal reactions. Use N/A for explicitly complete silence. Use non_diegetic_music for audience-only music, specifying instruments, tempo and dynamics where requested or useful. Use N/A when there is no score."""

_REF = """In subject_definitions, define each separately tracked visible element as <Subject N> and state its provenance. Use a separate <Picture N> definition only when the image itself anchors a frame or composition. Use <Video N> for a whole-video role and <Audio N> for referenced or reused sound. Keep labels in angle brackets and consistent across fields. Link referenced attributes to the actions and shots where they matter.
Start the summary body with a bracketed task, usually [reference generation] for appearance or style references. Add keyframe completion, video editing, video continuation, audio reuse or audio reference only when that role applies. Join simultaneous roles with ' + ' within the brackets. In retention_analysis, write a separate line for each definition with shot coverage and its relationship. Use fully_preserved for an unchanged defined visual attribute, partially_preserved for an intentional change, attribute_transfer when moved to a different subject, or weak_reference for broad resemblance. Preserve visual identity across changes in pose, setting, light or framing. Distinguish copied audio from guidance on sound.
For requested invented Chinese dialogue, favor a short setup, response, turn and closing reaction when timing permits. Use about four short lines if the scene supports them. Prioritize exact supplied dialogue and allow time for lip sync, pauses and visible acting."""

MODE_GUIDES = {
    "1ref2va": """Identify what the one supplied asset contributes. For a single character image, map <Picture 1> to the relevant <Subject 1> identity. Preserve face, hair, age, body proportions and any requested outfit. A reference with multiple visible elements may support separately defined subjects only where the brief uses them. Use it as a character or appearance reference unless the brief explicitly assigns it a frame role.""",
    "2ref2va": """Map both assets to their roles before writing the scene. For two distinct character images, bind <Picture 1> to <Subject 1> and <Picture 2> to <Subject 2>. Keep facial features, hair, costume, screen position and eyelines consistent. Combine assets in one definition when the brief establishes a shared identity or complementary attributes. Identify each speaker by vocal order, even when <Subject 2> speaks first. Appearance references do not establish target frames unless the brief assigns that use.""",
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
        _TIMELINE,
        _AUDIO,
    ]
    if fields == REF_FIELDS:
        parts.append(_REF)
    if mode in ALIGNMENTS:
        parts.append(f"Begin with this alignment line, followed by a blank line. Replace N with the last shot index and S.SS with the runtime to two decimal places wherever those placeholders occur.\n{ALIGNMENTS[mode]}")
    parts.append("Write these exact field names in order. Use plain text without a title or Markdown fence.\n" + "\n".join(field + ":" for field in fields))
    return "\n\n".join(parts)
