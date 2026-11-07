import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sbp_library import SBPFile, SBPLibrary  # noqa: E402
from song_extraction_library import SongExtractor  # noqa: E402


def _backup(tmp_path: Path, song_count: int) -> Path:
    lib = SBPLibrary()
    songs = [lib.create_song(f"Song {n}", id=100 + n) for n in range(song_count)]
    path = tmp_path / "backup.sbp"
    lib.save_sbp_file(SBPFile(songs=songs), path)
    return path


def _validated(song_ids):
    return [{"title": f"Song {i - 100}", "validated": True, "song_id": i} for i in song_ids]


def test_multi_set_items_have_file_wide_unique_ids(tmp_path):
    extractor = SongExtractor("user", _backup(tmp_path, 12))
    validated = {
        "sets": [
            {"name": "Set 1", "songs": _validated(range(100, 105))},
            {"name": "Set 2", "songs": _validated(range(105, 109))},
            {"name": "Set 3", "songs": _validated(range(109, 111))},
        ],
        "extras": _validated([111]),
    }

    out = tmp_path / "out.sbp"
    extractor.extract_and_save(validated, out, "Nov 07 Two Lane")
    sbp = SBPLibrary().load_sbp_file(out)

    assert [s.name for s in sbp.sets] == [
        "Nov 07 Two Lane S1",
        "Nov 07 Two Lane S2",
        "Nov 07 Two Lane S3",
        "Nov 07 Two Lane X",
    ]
    assert [s.id for s in sbp.sets] == [1, 2, 3, 4]

    items = [item for s in sbp.sets for item in s.items]
    assert [item.id for item in items] == list(range(1, 13))
    for s in sbp.sets:
        assert all(item.set_id == s.id for item in s.items)
        assert [item.order for item in s.items] == list(range(len(s.items)))

    sync_ids = [s.sync_id for s in sbp.sets] + [item.sync_id for item in items]
    assert all(sync_ids)
    assert len(set(sync_ids)) == len(sync_ids)


def test_regenerating_gives_new_sync_ids(tmp_path):
    extractor = SongExtractor("user", _backup(tmp_path, 3))
    validated = {"sets": [{"name": "Set 1", "songs": _validated(range(100, 103))}]}

    first = extractor.create_sbp_file(validated, "Gig")
    second = extractor.create_sbp_file(validated, "Gig")

    assert first.sets[0].sync_id != second.sets[0].sync_id
