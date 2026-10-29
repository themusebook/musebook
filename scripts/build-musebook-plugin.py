"""Validate and deterministically package the standalone Musebook plugin."""
from pathlib import Path
import hashlib
import json
import struct
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/musebook"
RELEASES = ROOT / "plugins/releases"


def build():
    portable = json.loads((PLUGIN / "plugin.json").read_text())
    codex = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
    interface = portable["extensions"]["com.openai"]["interface"]
    assert interface == codex["interface"], "Manifest interfaces differ"
    assert portable["version"] == codex["version"]
    assert len(interface["shortDescription"]) <= 30
    prompts = interface["defaultPrompt"]
    assert isinstance(prompts, list) and 1 <= len(prompts) <= 3, "Use one to three starter prompts"
    assert all(isinstance(prompt, str) and prompt.strip() for prompt in prompts), "Starter prompts must be nonempty strings"
    assert interface["supportURL"].startswith("https://")
    assert "https://clawd-ws.fly.dev/" in interface["longDescription"]
    for name in ["mcp.json", ".mcp.json"]:
        servers = json.loads((PLUGIN / name).read_text())["mcpServers"]
        connection_type = "streamable-http" if name == "mcp.json" else "http"
        assert servers == {
            "musebook-account": {"type": connection_type, "url": "https://musebook.trade/mcp-auth"}
        }, "Musebook must use one OAuth account connection"
    skills = list((PLUGIN / "skills").rglob("SKILL.md"))
    assert len(skills) == 1
    assert "https://clawd-ws.fly.dev/" in skills[0].read_text()
    assert "stream_launches" in skills[0].read_text()
    # Validate every PNG chunk CRC and require an intact terminal IEND chunk.
    logo = (PLUGIN / "assets/logo.png").read_bytes()
    assert logo[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    kind = None
    while offset < len(logo):
        length = struct.unpack(">I", logo[offset:offset + 4])[0]
        chunk = logo[offset + 4:offset + 8 + length]
        crc = struct.unpack(">I", logo[offset + 8 + length:offset + 12 + length])[0]
        assert zlib.crc32(chunk) == crc, "Invalid PNG chunk"
        kind = chunk[:4]
        offset += 12 + length
    assert kind == b"IEND" and offset == len(logo)
    files = []
    for path in sorted(PLUGIN.rglob("*")):
        assert not path.is_symlink(), f"Symlink: {path}"
        if path.is_file():
            assert path.name not in {".DS_Store", ".env"}
            if path.suffix == ".json":
                json.loads(path.read_text())
            files.append(path)
    RELEASES.mkdir(exist_ok=True)
    archive = RELEASES / "musebook-plugin.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for path in files:
            info = zipfile.ZipInfo("musebook/" + path.relative_to(PLUGIN).as_posix(),
                                   date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            out.writestr(info, path.read_bytes())
    with zipfile.ZipFile(archive) as out:
        assert out.testzip() is None
        assert len(out.namelist()) == len(files)
        for path in files:
            assert out.read("musebook/" + path.relative_to(PLUGIN).as_posix()) == path.read_bytes()
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest_path = RELEASES / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    package = next(p for p in manifest["packages"] if p["name"] == "musebook")
    package.update(version=portable["version"], sha256=digest,
                   bytes=archive.stat().st_size, skills=len(skills),
                   discoverableSkills=len(skills), files=len(files))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(package, indent=2))


if __name__ == "__main__":
    build()
