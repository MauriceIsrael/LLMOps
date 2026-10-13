"""Reference embedding models of the Hub: pinned files, offline download, integrity check (issue #94, lot E1).

The server never calls the network at query time: the model files are fetched **once** (``kb models fetch``, or the
Docker build) into ``data/models/`` (git-ignored), and every file is checked against the SHA-256 pinned here before it
is loaded. A file that does not match is never loaded: the Hub falls back to its lexical ranking.

Standard library only, so the Docker build can run this module on its own (``python pipelines/similarity/models.py
fetch``) in a cached layer, before the application code is copied.

Behind a proxy that inspects HTTPS (corporate network, antivirus, WSL without the host's certificates), the TLS
verification is never disabled (issue #111). Instead:

* ``KB_MODELS_CA_BUNDLE`` (or ``SSL_CERT_FILE``, ``REQUESTS_CA_BUNDLE``) names a PEM file of extra trusted
  certificates, e.g. the proxy's root certificate, added to the default ones;
* ``KB_MODELS_BASE_URL`` (or ``HF_ENDPOINT``) points to a mirror of huggingface.co (same URL layout);
* ``fetch(..., source_dir=...)`` installs files downloaded elsewhere (``kb models fetch --from-dir``), checked against
  the same SHA-256 (``kb models urls`` lists what to download).

Proxies are taken from ``HTTPS_PROXY`` / ``NO_PROXY`` as usual.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODELS_DIR = Path("data/models")
HF_BASE = "https://huggingface.co"


@dataclass(frozen=True)
class ModelSpec:
    """A reference model: where its files come from (pinned revision) and what they must hash to."""

    id: str
    version: str  # revision of the source repository, pinned
    repo: str
    files: dict[str, str]  # remote path -> sha256 (stored flat under the model directory)
    model_file: str  # the ONNX graph among ``files`` (its sha256 identifies the model)
    dim: int
    query_prefix: str = ""
    passage_prefix: str = ""
    license: str = ""
    # Cosine similarities of a model live in a narrow band; ``floor``/``ceil`` map that band onto [0, 1] so that a
    # threshold means the same thing whatever the model (calibrated on tests/fixtures/similarity/fr-en-doctrine.yaml).
    floor: float = 0.0
    ceil: float = 1.0
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def dirname(self) -> str:
        return self.id.replace("/", "__")

    @property
    def sha256(self) -> str:
        return self.files.get(self.model_file, "")

    def local_name(self, remote: str) -> str:
        return remote.rsplit("/", 1)[-1]


E5_SMALL = ModelSpec(
    id="intfloat/multilingual-e5-small",
    version="614241f622f53c4eeff9890bdc4f31cfecc418b3",
    repo="intfloat/multilingual-e5-small",
    files={
        "onnx/model_qint8_avx512_vnni.onnx": "dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88",
        "onnx/tokenizer.json": "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
        "onnx/config.json": "bbb7c1333fc4b3e27fbc9cd5d2070aabcc1d4dfb99917c3633e772f97545a6b6",
        "onnx/special_tokens_map.json": "d05497f1da52c5e09554c0cd874037a083e1dc1b9cfd48034d1c717f1afc07a7",
        "onnx/tokenizer_config.json": "a1d6bc8734a6f635dc158508bef000f8e2e5a759c7d92f984b2c86e5ff53425b",
    },
    model_file="onnx/model_qint8_avx512_vnni.onnx",
    dim=384,
    query_prefix="query: ",
    passage_prefix="passage: ",
    license="MIT",
    floor=0.70,
    ceil=0.95,
)

# The toy encoder of the tests (hashed bag of words): no file, no semantics, deterministic.
TOY_BOW = ModelSpec(id="toy-bow", version="1", repo="", files={}, model_file="", dim=128)

MODELS: dict[str, ModelSpec] = {E5_SMALL.id: E5_SMALL, TOY_BOW.id: TOY_BOW}
DEFAULT_MODEL = E5_SMALL.id


def spec_for(model_id: str | None) -> ModelSpec:
    model_id = (model_id or DEFAULT_MODEL).strip()
    if model_id not in MODELS:
        raise ValueError(f"unknown embedding model '{model_id}' (known: {sorted(MODELS)}).")
    return MODELS[model_id]


def model_dir(spec: ModelSpec, models_dir: str | Path | None = None) -> Path:
    return Path(models_dir or DEFAULT_MODELS_DIR) / spec.dirname


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_VERIFIED: dict[tuple[str, int, int], str] = {}


def _cached_sha256(path: Path) -> str:
    """SHA-256 of a file, computed once per (path, size, mtime) in the process."""
    st = path.stat()
    key = (str(path.resolve()), st.st_size, st.st_mtime_ns)
    if key not in _VERIFIED:
        _VERIFIED[key] = file_sha256(path)
    return _VERIFIED[key]


def verify(spec: ModelSpec, models_dir: str | Path | None = None) -> list[str]:
    """Problems of the local copy of ``spec`` (empty: present and intact)."""
    base = model_dir(spec, models_dir)
    problems = []
    for remote, expected in sorted(spec.files.items()):
        path = base / spec.local_name(remote)
        if not path.is_file():
            problems.append(f"missing {path}")
        elif _cached_sha256(path) != expected:
            problems.append(f"sha256 mismatch for {path} (expected {expected[:12]}…)")
    return problems


CA_BUNDLE_VARS = ("KB_MODELS_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE")


class CertificateError(RuntimeError):
    """The download was refused because the server's certificate is not trusted (proxy inspecting HTTPS?)."""


def base_url() -> str:
    return (os.getenv("KB_MODELS_BASE_URL") or os.getenv("HF_ENDPOINT") or HF_BASE).rstrip("/")


def file_urls(spec: ModelSpec) -> dict[str, str]:
    """Local file name -> download URL of every pinned file (pinned revision: the bytes never change)."""
    return {spec.local_name(r): f"{base_url()}/{spec.repo}/resolve/{spec.version}/{r}" for r in sorted(spec.files)}


def ssl_context() -> ssl.SSLContext:
    """Default trust store, plus the PEM bundle named by ``KB_MODELS_CA_BUNDLE`` (or SSL_CERT_FILE, REQUESTS_CA_BUNDLE).

    Verification stays on: an extra bundle only adds trusted roots, such as the one of a proxy inspecting HTTPS.
    """
    ctx = ssl.create_default_context()
    for var in CA_BUNDLE_VARS:
        bundle = os.getenv(var)
        if bundle:
            if not Path(bundle).is_file():
                raise CertificateError(f"{var}={bundle}: no such certificate file.")
            ctx.load_verify_locations(cafile=bundle)
            break
    return ctx


CERTIFICATE_HELP = (
    "the certificate presented for {host} is not trusted ({reason}). A proxy or an antivirus probably inspects HTTPS "
    "on this network. Verification is never disabled; instead either:\n"
    "  1. export KB_MODELS_CA_BUNDLE=/path/to/proxy-root.pem (the proxy's root certificate, PEM) and run again;\n"
    "  2. export KB_MODELS_BASE_URL=https://<mirror of huggingface.co> if your organisation has one;\n"
    "  3. download the files listed by 'kb models urls' with a browser, then 'kb models fetch --from-dir <folder>'\n"
    "     (each file is checked against its pinned SHA-256)."
)


def _download(url: str, partial: Path, context: ssl.SSLContext) -> None:
    try:
        with urllib.request.urlopen(url, timeout=60, context=context) as resp, partial.open("wb") as out:  # noqa: S310
            shutil.copyfileobj(resp, out, length=1 << 20)
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(exc, ssl.SSLCertVerificationError) or isinstance(reason, ssl.SSLCertVerificationError):
            partial.unlink(missing_ok=True)
            host = urllib.parse.urlsplit(url).hostname or url
            raise CertificateError(CERTIFICATE_HELP.format(host=host, reason=getattr(reason, "verify_message", None)
                                                           or reason)) from exc
        raise


def fetch(spec: ModelSpec, models_dir: str | Path | None = None, force: bool = False, quiet: bool = False,
          source_dir: str | Path | None = None) -> Path:
    """Install the pinned files of ``spec`` (only those missing or corrupt) and check them.

    From the network (here only), or from ``source_dir`` when the files were downloaded elsewhere; either way a file
    whose SHA-256 differs from the pinned one is never installed.
    """
    base = model_dir(spec, models_dir)
    base.mkdir(parents=True, exist_ok=True)
    context = ssl_context() if source_dir is None else None
    urls = file_urls(spec)
    for remote, expected in sorted(spec.files.items()):
        name = spec.local_name(remote)
        target = base / name
        if not force and target.is_file() and file_sha256(target) == expected:
            continue
        partial = target.with_name(target.name + ".part")
        if source_dir is not None:
            source = Path(source_dir) / name
            if not source.is_file():
                raise RuntimeError(f"{source}: missing (download it from {urls[name]}).")
            if not quiet:
                print(f"copying {source}", flush=True)
            shutil.copyfile(source, partial)
        else:
            if not quiet:
                print(f"downloading {urls[name]}", flush=True)
            assert context is not None
            _download(urls[name], partial, context)
        actual = file_sha256(partial)
        if actual != expected:
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"{remote}: sha256 {actual} does not match the pinned {expected}; nothing installed.")
        os.replace(partial, target)
    problems = verify(spec, models_dir)
    if problems:
        raise RuntimeError("; ".join(problems))
    return base


def main(argv: list[str] | None = None) -> int:
    """``python pipelines/similarity/models.py fetch [model_id] [models_dir]`` (used by the Dockerfile)."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ("fetch", "verify"):
        print("usage: models.py fetch|verify [model_id] [models_dir]")
        return 2
    spec = spec_for(args[1] if len(args) > 1 else None)
    target = args[2] if len(args) > 2 else None
    if args[0] == "fetch":
        path = fetch(spec, target)
        print(f"{spec.id}@{spec.version[:12]} ready in {path} (sha256 {spec.sha256})")
        return 0
    problems = verify(spec, target)
    print("\n".join(problems) or f"{spec.id} intact")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
