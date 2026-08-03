from pathlib import Path

from house_brain.memory import MemoryInput, MemoryStore


def test_memory_store_upserts_searches_and_forgets(tmp_path: Path) -> None:
    store = MemoryStore(str(tmp_path / "memory.db"))

    created = store.remember(
        MemoryInput(
            key="profile.profession",
            value="Vincenzo è falegname",
            category="profile",
            importance=9,
        )
    )
    updated = store.remember(
        MemoryInput(
            key="profile.profession",
            value="Vincenzo lavora come falegname",
            category="profile",
            importance=10,
        )
    )

    assert created.id == updated.id
    assert updated.value == "Vincenzo lavora come falegname"
    assert len(store.search("falegname")) == 1
    assert store.search()[0].importance == 10
    assert store.forget("profile.profession") is True
    assert store.search() == []
    assert store.forget("profile.profession") is False
