"""Model download behind a proxy inspecting HTTPS (issue #111): extra CA bundle, mirror, offline install.

TLS verification is never disabled; a certificate failure explains the three ways out.
"""

import hashlib
import ssl
import urllib.error

import pytest

from pipelines.similarity import models as models_mod
from pipelines.similarity.models import CertificateError, ModelSpec, fetch, file_urls, ssl_context

CONTENT = {"model.onnx": b"onnx-bytes", "tokenizer.json": b"{}"}
SPEC = ModelSpec(id="test/tiny", version="abc123", repo="test/tiny",
                 files={f"onnx/{n}": hashlib.sha256(b).hexdigest() for n, b in CONTENT.items()},
                 model_file="onnx/model.onnx", dim=4)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("KB_MODELS_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "KB_MODELS_BASE_URL", "HF_ENDPOINT"):
        monkeypatch.delenv(var, raising=False)


def test_install_from_a_folder_checks_every_file(tmp_path):
    source = tmp_path / "downloads"
    source.mkdir()
    for name, data in CONTENT.items():
        (source / name).write_bytes(data)
    path = fetch(SPEC, tmp_path / "models", quiet=True, source_dir=source)
    assert sorted(p.name for p in path.iterdir()) == ["model.onnx", "tokenizer.json"]

    (source / "model.onnx").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="does not match the pinned"):
        fetch(SPEC, tmp_path / "other", quiet=True, source_dir=source)
    assert not (tmp_path / "other" / SPEC.dirname / "model.onnx").exists()  # nothing half-installed


def test_a_missing_file_in_the_folder_names_its_url(tmp_path):
    with pytest.raises(RuntimeError, match=r"missing \(download it from https://huggingface.co/test/tiny/resolve/abc123/"):
        fetch(SPEC, tmp_path / "models", quiet=True, source_dir=tmp_path)


def test_mirror_replaces_huggingface(monkeypatch):
    monkeypatch.setenv("KB_MODELS_BASE_URL", "https://mirror.example.org/hf/")
    assert file_urls(SPEC)["model.onnx"] == "https://mirror.example.org/hf/test/tiny/resolve/abc123/onnx/model.onnx"


def test_extra_ca_bundle_keeps_verification_on(monkeypatch, tmp_path):
    monkeypatch.setenv("KB_MODELS_CA_BUNDLE", str(tmp_path / "absent.pem"))
    with pytest.raises(CertificateError, match="no such certificate file"):
        ssl_context()
    loaded = []
    monkeypatch.setattr(ssl.SSLContext, "load_verify_locations", lambda self, cafile=None, **kw: loaded.append(cafile))
    bundle = tmp_path / "proxy-root.pem"
    bundle.write_text("-----BEGIN CERTIFICATE-----\n")
    monkeypatch.setenv("KB_MODELS_CA_BUNDLE", str(bundle))
    ctx = ssl_context()
    assert loaded[-1] == str(bundle)  # after the default trust store
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname


def test_a_certificate_failure_explains_the_ways_out(monkeypatch, tmp_path):
    def refuse(url, timeout, context):
        err = ssl.SSLCertVerificationError(1, "certificate verify failed")
        err.verify_message = "self-signed certificate in certificate chain"
        raise urllib.error.URLError(err)

    monkeypatch.setattr(models_mod.urllib.request, "urlopen", refuse)
    with pytest.raises(CertificateError) as exc:
        fetch(SPEC, tmp_path / "models", quiet=True)
    message = str(exc.value)
    assert "self-signed certificate in certificate chain" in message and "huggingface.co" in message
    assert "KB_MODELS_CA_BUNDLE" in message and "KB_MODELS_BASE_URL" in message and "--from-dir" in message
    assert not list((tmp_path / "models" / SPEC.dirname).glob("*.part"))
