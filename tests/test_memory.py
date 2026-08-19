from pathlib import Path

from house_brain.memory import MemoryInput, MemoryStore


def test_memory_store_upserts_searches_and_forgets(tmp_path: Path) -> None:
    store = MemoryStore(str(tmp_path / "memory.db"))

    created = store.remember(
        MemoryInput(
            key="profile.profession",
            value="The user works as a carpenter",
            category="profile",
            importance=9,
        )
    )
    updated = store.remember(
        MemoryInput(
            key="profile.profession",
            value="The user works professionally as a carpenter",
            category="profile",
            importance=10,
        )
    )

    assert created.id == updated.id
    assert updated.value == "The user works professionally as a carpenter"
    assert len(store.search("carpenter")) == 1
    assert store.search("professionally")[0].key == "profile.profession"
    assert store.search("unrelated query") == []
    assert store.search()[0].importance == 10
    assert store.forget("profile.profession") is True
    assert store.search() == []
    assert len(store.search(deleted=True)) == 1
    assert store.forget("profile.profession") is False
    assert store.restore("profile.profession") is True
    assert len(store.search()) == 1
    assert store.restore("profile.profession") is False
