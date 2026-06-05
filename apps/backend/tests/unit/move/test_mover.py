from app.move.mover import move_file


def test_move_overwrites_existing_target_on_collision(tmp_path):
    """move_file replaces an existing target file (deliberate overwrite, no suffixing).

    The old test expected a "_v<timestamp>" collision suffix, but the mover was
    reworked to overwrite on collision so re-processing a book replaces its prior
    output rather than accumulating versioned copies. See DMI-111.
    """
    src = tmp_path / "a.fb2"
    src.write_text("new content")

    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "a.fb2").write_text("old content")
    (dst / "a_v20260101_1200_v1.fb2").write_text("unrelated sibling")

    result = move_file(src, dst, "a.fb2")

    assert result.exists()
    # Overwrites the colliding target in place — no suffix appended.
    assert result.name == "a.fb2"
    assert result.read_text() == "new content"
    # The unrelated sibling file is untouched.
    assert (dst / "a_v20260101_1200_v1.fb2").read_text() == "unrelated sibling"
    # The source has been moved away.
    assert not src.exists()
