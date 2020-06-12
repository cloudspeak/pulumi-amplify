import binascii
import os
from math import ceil


class RandomId:
    """
    Class for generating random IDs to append to AWS resource names, preventing
    conflicts.
    """

    @staticmethod
    def generate(chars):
        char_bytes = ceil(chars / 2)
        string = binascii.b2a_hex(os.urandom(char_bytes)).decode("utf-8")
        return string[0:chars]
