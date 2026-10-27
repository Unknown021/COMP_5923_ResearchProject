Prompt used with Claude to generate filler episodes. Keep this file versioned:
it goes in the paper's appendix.

---

You are writing filler scenes for a roleplay transcript used in a research study.

The model's character is defined by this card:

<character_card>
{character_card}
</character_card>

Write {n_episodes} self-contained scene episodes from a single overland journey,
like an episodic D&D session log. Each episode is roughly {tokens_per_episode}
tokens and alternates user turns (the player, describing actions in second
person) and assistant turns (the character, in their voice as defined above).

Constraints:
- Each episode must make sense on its own; later episodes must not depend on
  details from earlier ones.
- Assistant turns must stay consistent with the card's speech, traits and backstory.
- Do NOT use any of these strings anywhere: {forbidden_strings}
- Do NOT name any of these NPCs: {forbidden_npcs}

Output a JSON array. Each element:
{{"id": "<name>_eNNN", "title": "...", "turns": [{{"role": "user", "content": "..."}}, {{"role": "assistant", "content": "..."}}]}}
