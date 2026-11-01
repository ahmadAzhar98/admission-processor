from synthetic.fonts import is_urdu, load_font


def test_is_urdu():
    assert is_urdu("نام")
    assert is_urdu("Name / نام")
    assert not is_urdu("Name")


def test_load_font_always_returns_a_font(monkeypatch, tmp_path):
    monkeypatch.setenv("AP_SYNTHETIC_FONT", str(tmp_path / "missing.ttf"))
    load_font.cache_clear()
    font = load_font(20)
    assert font.getbbox("Ag")[3] > 0
    load_font.cache_clear()
