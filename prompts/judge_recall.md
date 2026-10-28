You are checking whether a reply from a roleplay character correctly recalls one
specific fact. Ignore style, tone, and roleplay flavor; judge only the answer.

<question>
{question}
</question>

<correct_answer>
{canonical_answer}
</correct_answer>

<accepted_variants>
{aliases}
</accepted_variants>

<reply>
{response}
</reply>

The reply is CORRECT only if it gives the correct answer (or an accepted variant,
paraphrase, or spelling variant of it) as its answer to the question.

The reply is INCORRECT if it:
- gives a different answer, even if it also mentions the correct one
  (e.g., "Clover. Not Thistlewick." asserts Clover);
- rejects or doubts the correct answer;
- hedges between several candidate answers without committing to the correct one;
- says it does not know, or does not answer.

First explain your reasoning in one or two sentences, then give the verdict.
