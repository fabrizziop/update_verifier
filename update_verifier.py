from __future__ import print_function
import os
import sys
from pyasn1.codec.der.decoder import decode as der_decoder
import rsa

FOOTER_SIZE = 6
EOCD_HEADER_SIZE = 22

class SignedFile(object):
    def __init__(self, filepath):
        self.eocd = None
        self.eocd_size = None
        self.filepath = filepath
        self.footer = None
        self.length = os.path.getsize(filepath)
        self.signed_len = None
        self.signature_start = None

    def get_footer(self):
        with open(self.filepath, 'rb') as zipfile:
            zipfile.seek(-FOOTER_SIZE, os.SEEK_END)
            self.footer = bytearray(zipfile.read())

    def check_footer(self):
        if self.footer is None:
            self.get_footer()
        comment_size = self.footer[4] + (self.footer[5] << 8)
        self.signature_start = self.footer[0] + (self.footer[1] << 8)
        self.eocd_size = comment_size + EOCD_HEADER_SIZE
        assert self.footer[2] == 255 and self.footer[3] == 255, (
            "Footer has wrong magic")
        assert self.signature_start <= comment_size, (
            "Signature start larger than comment")
        assert self.signature_start > FOOTER_SIZE, (
            "Signature inside footer or outside file")
        assert self.length >= self.eocd_size, "EOCD larger than length"
        self.signed_len = self.length - self.eocd_size + EOCD_HEADER_SIZE - 2

    def check_eocd(self):
        if self.footer is None:
            self.check_footer()
        with open(self.filepath, 'rb') as zipfile:
            zipfile.seek(-self.eocd_size, os.SEEK_END)
            self.eocd = bytearray(zipfile.read(self.eocd_size))
            assert self.eocd[0:4] == bytearray([80, 75, 5, 6]), (
                "EOCD has wrong magic")
            for i in range(0, self.eocd_size-1):
                zipfile.seek(-i, os.SEEK_END)
                assert bytearray(zipfile.read(4)) != bytearray([80, 75, 5, 6]), (
                    "Multiple EOCD magics - possible exploit")

    def verify(self, pubkey):
        self.check_eocd()
        with open(self.filepath, 'rb') as zipfile:
            # Read everything that's been signed
            zipfile.seek(0, os.SEEK_SET)
            message = zipfile.read(self.signed_len)
            # Read the signature
            zipfile.seek(-self.signature_start, os.SEEK_END)
            signature_size = self.signature_start - FOOTER_SIZE
            signature_raw = zipfile.read(signature_size)
        # pyasn1 can't decode PKCS#7, so cert (tuple[0]) contains everything
        cert = der_decoder(signature_raw)[0]
        # since pyasn1 doesn't decode properly, we have to read this in a
        # stupid way. The data we need is the very last field of each entry
        signature = cert[-1][-1][-1]['field-4'].asOctets()
        with open(pubkey) as zipfile:
            keydata = rsa.PublicKey.load_pkcs1(zipfile.read())
        try:
            return rsa.verify(message, signature, keydata)
        except rsa.pkcs1.VerificationError:
            return False

def print_help():
    print("{} zip_to_verify public_key".format(sys.argv[0]))
    print("    public_key must be in PKCS#1 format")

def main():
    if len(sys.argv) != 3:
        print_help()
        sys.exit(2)
    zipfile = sys.argv[1]
    pubkey = sys.argv[2]
    signed_file = SignedFile(zipfile)
    if not signed_file.verify(pubkey):
        print("Failed verification", file=sys.stderr)
        sys.exit(1)
    else:
        print("File verified successfully", file=sys.stderr)
        sys.exit(0)

if __name__ == '__main__':
    main()
