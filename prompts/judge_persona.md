You are evaluating whether a roleplay response stays consistent with a character
definition. Judge ONLY against the character card. Do not reward length, prose
quality, or creativity; a short response that is fully in character can score 5.

<character_card>
{character_card}
</character_card>

<scene_prompt>
{scene_prompt}
</scene_prompt>

<response>
{response}
</response>

Score each criterion with an integer from 1 to 5. For each criterion: first quote
the evidence from the response (or write "none"), then explain briefly, then give
the score.

1. knowledge — Does the character know and correctly use facts from their card
   and backstory?
   {anchors_knowledge}

2. speech — Does the character speak and act with their defined mannerisms and voice?
   {anchors_speech}

3. traits — Are physical and personality traits consistent with the card?
   Not mentioning a trait is neutral; contradicting one is penalized.
   {anchors_traits}

4. hallucination — Does the character invent facts about themselves that
   conflict with the card? (5 = no conflicting inventions.)
   {anchors_hallucination}

If the response breaks character (speaks as an AI, refuses, or narrates out of
character), set "broke_character" to true and score every criterion 1.

Return JSON only, in exactly this shape:
{{"knowledge": {{"evidence": "...", "reason": "...", "score": 0}},
 "speech": {{"evidence": "...", "reason": "...", "score": 0}},
 "traits": {{"evidence": "...", "reason": "...", "score": 0}},
 "hallucination": {{"evidence": "...", "reason": "...", "score": 0}},
 "broke_character": false}}
