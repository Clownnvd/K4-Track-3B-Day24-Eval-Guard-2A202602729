"""Context expansion must remain grounded in retrieved local sources."""

from types import SimpleNamespace


def test_expands_ranked_source_without_losing_split_policy(tmp_path, monkeypatch):
    import config
    from scripts import setup_answers

    (tmp_path / "policy.md").write_text("# Policy\nApproval over 50 million: CEO.", encoding="utf-8")
    monkeypatch.setattr(setup_answers, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    ranked = [
        SimpleNamespace(text="first fragment", metadata={"source": "policy.md"}),
        SimpleNamespace(text="second fragment", metadata={"source": "policy.md"}),
        SimpleNamespace(text="untrusted", metadata={"source": "../outside.md"}),
    ]
    search = SimpleNamespace(search=lambda question: [
        SimpleNamespace(text="first fragment", score=1.0, metadata={"source": "policy.md"})
    ])
    reranker = SimpleNamespace(rerank=lambda question, rows, top_k: ranked)

    answer, contexts, mode, model = setup_answers.run_query("Who approves?", search, reranker, 3)

    assert len(contexts) == 2
    assert "Approval over 50 million: CEO." in contexts[0]
    assert contexts[1] == "untrusted"
    assert answer == contexts[0]
    assert (mode, model) == ("extractive_fallback", None)
