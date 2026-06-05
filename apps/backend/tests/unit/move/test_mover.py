from app.move.mover import move_file


def test_move_overwrites_existing_target_on_collision(tmp_path):
    """move_file replaces an existing target file (deliberate overwrite, no suffixing)."""
    src = tmp_path / "a.fb2"
    src.write_text("new content")

    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "a.fb2").write_text("old content")
    (dst / "a_v20260101_1200_v1.fb2").write_text("unrelated sibling")

    moved_path = move_file(src, dst, "a.fb2")

    assert moved_path.exists()
    assert moved_path.name == "a.fb2"
    assert moved_path.read_text() == "new content"
    assert (dst / "a_v20260101_1200_v1.fb2").read_text() == "unrelated sibling"
    assert not src.exists()
