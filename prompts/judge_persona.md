You are evaluating one character in a multi-character roleplay response. The response may
contain lines for several characters, each starting with a name and a colon, plus narration
lines with no name. Evaluate ONLY {target_name}: lines starting with "{target_first_name}:"
and narration that clearly describes {target_name}. Ignore every other character's lines.

Judge {target_name} only against their character card. Do not reward length, prose quality,
or creativity; a short reply that is fully in character can score 5.

<target_character>
{target_card}
</target_character>

<other_characters>
{other_cards}
</other_characters>

<scene_prompt>
{scene_prompt}
</scene_prompt>

<response>
{response}
</response>

Score each criterion with an integer from 1 to 5. For each criterion: first quote the
evidence from {target_name}'s lines (or write "none"), then explain briefly, then give
the score.

1. knowledge — Does {target_name} know and correctly use facts from their card and backstory?
   {anchors_knowledge}

2. speech — Does {target_name} speak and act with their defined mannerisms and voice?
   {anchors_speech}

3. traits — Are {target_name}'s physical and personality traits consistent with the card?
   Not mentioning a trait is neutral; contradicting one is penalized.
   {anchors_traits}

4. hallucination — Does {target_name} invent facts about themselves that conflict with
   the card? (5 = no conflicting inventions.)
   {anchors_hallucination}

5. distinctness — Does {target_name} stay distinct from the other characters? Use the
   other characters' cards only for this criterion.
   5 = nothing borrowed from another character; 3 = one minor borrowed phrase, habit, or
   trait; 1 = clearly speaks or acts like another character (uses their signature speech
   habit, physical trait, or backstory as their own).

If {target_name} does not appear in the response, set "target_absent" to true and score
every criterion 1. If the response breaks character (speaks as an AI, refuses, or steps
out of the story), set "broke_character" to true and score every criterion 1.

Return JSON only, in exactly this shape:
{{"knowledge": {{"evidence": "...", "reason": "...", "score": 0}},
 "speech": {{"evidence": "...", "reason": "...", "score": 0}},
 "traits": {{"evidence": "...", "reason": "...", "score": 0}},
 "hallucination": {{"evidence": "...", "reason": "...", "score": 0}},
 "distinctness": {{"evidence": "...", "reason": "...", "score": 0}},
 "target_absent": false,
 "broke_character": false}}
