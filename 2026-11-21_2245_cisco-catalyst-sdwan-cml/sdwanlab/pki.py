"""Our own enterprise Certificate Authority.

SD-WAN control connections (DTLS/TLS between edges and controllers) are
authenticated with certificates. Every control component gets a device
certificate signed by a CA that all the others trust. In production
that CA is usually Cisco PKI or your company's own PKI. In this lab we
create a small root CA right here, which is called "Enterprise Root CA"
mode in the Manager.

  1. create_root_ca()   - makes a private key + self-signed root cert
  2. the root cert is put into every controller's day-0 config and into
     the Manager settings, so everyone trusts it
  3. sign_csr()         - the Manager generates a CSR for each
     controller, we sign it, and hand the certificate back
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from .config import STATE

CA_KEY = STATE / "ca" / "root-ca.key"
CA_CRT = STATE / "ca" / "root-ca.crt"


def create_root_ca(org: str, days: int = 3650) -> str:
    """Create the root CA once and reuse it on later runs."""
    if CA_CRT.exists():
        return CA_CRT.read_text()
    CA_CRT.parent.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "SD-WAN Lab"),
        x509.NameAttribute(NameOID.COMMON_NAME, "SD-WAN Lab Root CA"),
    ])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)                       # self-signed: issuer == subject
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                                     content_commitment=False, key_encipherment=False,
                                     data_encipherment=False, key_agreement=False,
                                     encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    CA_KEY.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                         serialization.PrivateFormat.TraditionalOpenSSL,
                                         serialization.NoEncryption()))
    CA_KEY.chmod(0o600)
    CA_CRT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return CA_CRT.read_text()


def sign_csr(csr_pem: str, days: int = 730) -> str:
    """Sign a device CSR with our root CA and return the certificate (PEM).

    We keep the subject exactly as the device asked for it: the Manager
    checks that the certificate matches the CSR it generated.
    """
    ca_key = serialization.load_pem_private_key(CA_KEY.read_bytes(), password=None)
    ca_crt = x509.load_pem_x509_certificate(CA_CRT.read_bytes())
    csr = x509.load_pem_x509_csr(csr_pem.encode())
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_crt.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=days))
        .sign(ca_key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode()
