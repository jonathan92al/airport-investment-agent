"""Terminal chat for quick testing. Run: python -m airport_agent.cli"""
from .agent.core import Agent


def main():
    agent = Agent()
    print("Airport investment agent. Ctrl+C or 'exit' to quit.")
    while True:
        try:
            q = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit"}:
            break
        if q:
            r = agent.ask(q)
            print(f"\n[plan: {r.plan.model_dump(exclude_none=True, exclude_defaults=True)}]\n\n{r.text}")


if __name__ == "__main__":
    main()
