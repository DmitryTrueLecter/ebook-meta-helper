from move.mover import move_file


def test_move_with_multiple_collisions(tmp_path):
    src = tmp_path / "a.fb2"
    src.write_text("x")

    dst = tmp_path / "dst"
    dst.mkdir()

    (dst / "a.fb2").write_text("1")
    (dst / "a_v20260101_1200_v1.fb2").write_text("2")

    result = move_file(src, dst, "a.fb2")

    assert result.exists()
    assert "_v" in result.name
