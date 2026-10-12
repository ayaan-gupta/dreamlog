"""Milestone 1: record, transcribe, edit and save an entry."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from fastapi.testclient import TestClient

from dreamlog.audio import AudioDecodeError, decode_audio
from dreamlog.crypto import Cipher, generate_key, load_cipher
from dreamlog.main import create_app
from dreamlog.service import Dreamlog, NotFound, build_services, title_of
from dreamlog.transcribe import FakeTranscriber, FasterWhisperTranscriber

from .conftest import AUDIO, make_settings


def test_text_entry_round_trips(core: Dreamlog) -> None:
    saved = core.create_from_text("I found a   brass key\nin the garden.", illustrate=False)
    assert saved.transcript == "I found a brass key in the garden."
    assert saved.title == "I found a brass key in the garden"
    assert core.get_entry(saved.id).transcript == saved.transcript
    assert [e.id for e in core.list_entries()] == [saved.id]


def test_transcript_is_ciphertext_in_the_database(core: Dreamlog) -> None:
    saved = core.create_from_text("A wolf followed me across the frozen lake.", illustrate=False)
    with core.s.db.connect() as conn:
        row = conn.execute("SELECT transcript FROM entries WHERE id = %s", (saved.id,)).fetchone()
    assert row is not None
    blob = bytes(row["transcript"])
    assert b"wolf" not in blob and b"lake" not in blob
    assert core.s.cipher.decrypt_text(blob, context=saved.id.bytes) == saved.transcript


def test_ciphertext_cannot_be_moved_to_another_entry(core: Dreamlog) -> None:
    first = core.create_from_text("The first dream had a red door.", illustrate=False)
    second = core.create_from_text("The second dream had a blue door.", illustrate=False)
    with core.s.db.connect() as conn:
        conn.execute("UPDATE entries SET transcript = (SELECT transcript FROM entries WHERE id = %s) WHERE id = %s", (first.id, second.id))
    with pytest.raises(InvalidTag):
        core.get_entry(second.id)


def test_cipher_rejects_a_wrong_key_and_tampering() -> None:
    import base64

    cipher = Cipher(base64.urlsafe_b64decode(generate_key()), "environment")
    blob = cipher.encrypt_text("a staircase under the sea")
    assert cipher.decrypt_text(blob) == "a staircase under the sea"
    other = Cipher(base64.urlsafe_b64decode(generate_key()), "environment")
    with pytest.raises(InvalidTag):
        other.decrypt_text(blob)
    with pytest.raises(InvalidTag):
        cipher.decrypt_text(blob[:-1] + bytes([blob[-1] ^ 1]))


def test_a_key_is_generated_once_when_none_is_configured(tmp_path: Path) -> None:
    first = load_cipher("", tmp_path)
    second = load_cipher("", tmp_path)
    assert first.source == "generated"
    assert (tmp_path / "dev.key").stat().st_mode & 0o777 == 0o600
    assert second.decrypt_text(first.encrypt_text("same key")) == "same key"


def test_audio_is_deleted_after_transcription_by_default(core: Dreamlog) -> None:
    saved = core.create_from_audio((AUDIO / "clip-short.m4a").read_bytes(), ".m4a")
    assert saved.source == "voice" and not saved.has_audio
    assert saved.engines["transcriber"] == "fake"
    assert core.s.store.list("audio/") == []
    assert list((core.settings.data_dir / "tmp").iterdir()) == []


def test_audio_is_kept_encrypted_when_retention_is_on(tmp_path: Path) -> None:
    kept = Dreamlog(build_services(make_settings(tmp_path, keep_audio=True)))
    kept.delete_all()
    try:
        raw = (AUDIO / "clip-short.m4a").read_bytes()
        saved = kept.create_from_audio(raw, ".m4a")
        assert saved.has_audio
        (key,) = kept.s.store.list("audio/")
        assert kept.s.store.get(key) == raw
        on_disk = (tmp_path / "objects" / key).read_bytes()
        assert on_disk != raw and raw[:64] not in on_disk
    finally:
        kept.s.db.close()


def test_editing_replaces_transcript_symbols_and_mood(core: Dreamlog) -> None:
    saved = core.create_from_text("I was terrified. A wolf stood at the door.", illustrate=False)
    assert {s.name for s in saved.symbols} == {"wolf", "door"}
    assert saved.moods == ["fearful"]
    edited = core.update_entry(saved.id, "I felt calm. A whale passed under the bridge.")
    assert {s.name for s in edited.symbols} == {"whale", "bridge"}
    assert edited.moods == ["calm"]
    assert edited.updated_at > saved.updated_at and edited.created_at == saved.created_at
    with core.s.db.connect() as conn:
        left = {r["canonical"] for r in conn.execute("SELECT canonical FROM symbols").fetchall()}
    assert left == {"whale", "bridge"}, "words edited out of a dream must not linger in the symbol tables"


def test_missing_and_empty_entries_are_refused(core: Dreamlog) -> None:
    import uuid

    with pytest.raises(NotFound):
        core.get_entry(uuid.uuid4())
    with pytest.raises(ValueError, match="needs some words"):
        core.create_from_text("   \n ")


def test_a_file_that_is_not_audio_is_reported_not_crashed_on(tmp_path: Path) -> None:
    junk = tmp_path / "junk.webm"
    junk.write_bytes(b"this is not audio at all" * 40)
    with pytest.raises(AudioDecodeError):
        decode_audio(junk)


def test_decoding_gives_sixteen_kilohertz_mono() -> None:
    samples = decode_audio(AUDIO / "clip-short.m4a")
    assert samples.dtype.name == "float32" and samples.ndim == 1
    assert 3.5 < len(samples) / 16_000 < 6.0
    assert float(abs(samples).max()) <= 1.0


def test_title_is_the_first_sentence_cut_at_a_word() -> None:
    assert title_of("Short one. And more.") == "Short one"
    long = title_of("I was walking along a very long corridor that never seemed to end no matter how far I went.")
    assert long.endswith("…") and len(long) <= 65 and not long[:-1].endswith(" ")


def test_http_record_edit_save_flow(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path), warm=False)
    with TestClient(app) as client:
        client.delete("/api/all", params={"confirm": "delete-everything"})
        with (AUDIO / "clip-short.m4a").open("rb") as fh:
            made = client.post("/api/entries/audio", files={"file": ("dream.m4a", fh, "audio/mp4")})
        assert made.status_code == 201, made.text
        entry = made.json()
        assert entry["transcript"] == FakeTranscriber().script
        assert entry["image_url"].startswith(f"/api/entries/{entry['id']}/image")
        assert set(entry["timings_ms"]) >= {"transcribe", "extract", "embed", "canonicalise", "illustrate", "total"}

        edited = client.put(f"/api/entries/{entry['id']}", json={"text": "I was walking by the sea and found a red door."})
        assert edited.status_code == 200 and "red door" in edited.json()["transcript"]

        image = client.get(edited.json()["image_url"])
        assert image.status_code == 200 and image.headers["content-type"] == "image/webp" and image.content[:4] == b"RIFF"
        assert "private" in image.headers["cache-control"]

        assert client.post("/api/entries/audio", files={"file": ("x.webm", b"not audio" * 30, "audio/webm")}).status_code == 400
        assert client.post("/api/entries", json={"text": ""}).status_code == 422
        assert client.delete(f"/api/entries/{entry['id']}").status_code == 204
        assert client.get(f"/api/entries/{entry['id']}").status_code == 404


@pytest.mark.model
def test_real_whisper_transcribes_a_spoken_clip(whisper: FasterWhisperTranscriber) -> None:
    """Synthetic speech from the macOS ``say`` command, so a clean voice. The
    bar is a word-level match with the script, not an exact string."""
    heard = whisper.transcribe(AUDIO / "clip-short.m4a")
    said = (AUDIO / "clip-short.txt").read_text()

    def words(text: str) -> list[str]:
        return re.findall(r"[a-z']+", text.lower())

    ratio = difflib.SequenceMatcher(None, words(said), words(heard.text)).ratio()
    print(f"\nheard: {heard.text!r}\nword match with the script: {ratio:.3f}, clip {heard.duration_s:.1f}s")
    assert ratio > 0.9
    assert 3.5 < heard.duration_s < 6.0
