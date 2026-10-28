You are writing filler scenes for a roleplay transcript used in a research study on how
well language models remember facts and stay in character over long conversations.

The story:
{setting}

The model under test voices all of these characters at once:

{character_profiles}

Write {n_episodes} self-contained scene episodes from this journey, like an episodic
tabletop session log. Each episode is roughly {tokens_per_episode} tokens long and has
3 to 5 exchanges. An exchange is one user turn followed by one assistant turn.

User turns: the player's character, a hired guard, describes what they do and say, in
the first person ("I climb onto the wagon..."). Never write for the named characters here.

Assistant turns: the named characters react. Put each character's speech and actions on
its own line, starting with their first name and a colon, for example:
{format_example}
Narration that belongs to no character goes on its own line with no name. Most assistant
turns should include at least two of the characters, and across each episode all
{n_characters} should speak. Every character must stay consistent with their profile,
including their speech habits, and must sound clearly different from the others.

Constraints:
- Each episode must make sense on its own; never refer to events from other episodes.
- Keep the episodes varied: travel, weather, camp life, towns, small troubles on the road.
- Do NOT use any of these words or names anywhere: {forbidden_terms}

Return the episodes in the requested JSON format. Give each a short title.
