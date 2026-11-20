from diviso.memory.rag import RagIndex, chunk_text
from diviso.memory.store import MemoryStore


def make_store(tmp_path):
    return MemoryStore(tmp_path / "m.db", tmp_path / "MEMORY.md")


def test_fact_roundtrip(tmp_path):
    store = make_store(tmp_path)
    store.set_fact("name", "Diviso")
    assert store.get_fact("name") == "Diviso"
    assert store.list_facts() == {"name": "Diviso"}
    store.set_fact("name", "Diviso 2")
    assert store.get_fact("name") == "Diviso 2"
    store.close()


def test_memory_md_export_import_roundtrip(tmp_path):
    store = make_store(tmp_path)
    store.set_fact("editor", "vim")
    store.set_fact("lang", "python")
    md = store.export_to_markdown()
    assert "- editor: vim" in md.read_text()
    store2 = MemoryStore(tmp_path / "other.db", md)
    assert store2.import_from_markdown() == 2
    assert store2.get_fact("lang") == "python"
    store.close(); store2.close()


def test_chunking_overlap_and_size():
    chunks = chunk_text("x" * 1200, size=500, overlap=50)
    assert len(chunks) == 3
    assert all(len(c) <= 500 for c in chunks)


def test_rag_search_ranks_relevant_first(tmp_path):
    (tmp_path / "cats.md").write_text("Cats are small domestic animals. "
                                      "Cats sleep for many hours a day.")
    (tmp_path / "stocks.md").write_text("Stock markets trade shares of companies. "
                                        "Investors buy and sell stocks daily.")
    rag = RagIndex(tmp_path / "rag.db")
    rag.add_document(tmp_path / "cats.md")
    rag.add_document(tmp_path / "stocks.md")
    hits = rag.search("domestic animals that sleep")
    assert hits and hits[0]["doc"].endswith("cats.md")
    rag.close()


def test_rag_index_persists(tmp_path):
    doc = tmp_path / "note.txt"
    doc.write_text("Diviso is a local first agent framework.")
    rag = RagIndex(tmp_path / "rag.db")
    assert rag.add_document(doc) == 1
    rag.close()
    rag2 = RagIndex(tmp_path / "rag.db")
    assert rag2.count() == 1
    assert rag2.search("local agent")
    rag2.close()


def test_rag_empty_index_search():
    import tempfile, pathlib
    rag = RagIndex(pathlib.Path(tempfile.mkdtemp()) / "r.db")
    assert rag.search("anything") == []
    rag.close()
