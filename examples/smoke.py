"""Optional live test: requires SIMPLEX_API_TOKEN; consumes API usage."""

from simplex_ai import Choice, ChoiceAnswer, SimplexClient

with SimplexClient() as client:
    catalog = client.models()
    print("Model catalog received:", bool(catalog))
    response = client.system_one(
        state="2 + 2 = ?",
        questions={"answer": Choice(criteria={"four": "4", "five": "5"})},
    )
    answer = response.answers["answer"]
    assert isinstance(answer, ChoiceAnswer)
    assert answer.choice == "four", answer.choice
    print("Decision verified; usage:", response.usage)
