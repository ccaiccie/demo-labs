#!/bin/sh
# sign.sh NAME  ->  signs NAME.csr with the lab root CA, writes NAME.crt
openssl x509 -req -in "$1.csr" -CA root-ca.crt -CAkey root-ca.key -CAcreateserial \
  -days 730 -sha256 -out "$1.crt"
openssl x509 -in "$1.crt" -noout -subject -issuer -enddate
