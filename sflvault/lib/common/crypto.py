# -=- encoding: utf-8 -=-
#
# SFLvault - Secure networked password store and credentials manager.
#
# Copyright (C) 2008  Savoir-faire Linux inc.
#
# Author: Alexandre Bourget <alexandre.bourget@savoirfairelinux.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Provides function to serialize and unserialize cryptographic blobs"""

from Crypto.PublicKey import ElGamal
from Crypto.Cipher import AES, Blowfish
from Crypto.Util import randpool
from Crypto.Util.number import long_to_bytes, bytes_to_long
from base64 import b64decode, b64encode


#
# Random number generators setup
#
pool = randpool.RandomPool()
pool.stir()
pool.randomize()
randfunc = pool.get_bytes # We'll use this func for most of the random stuff


#
# Deal with ElGamal pubkey and messages serialization.
#
# TODO: DRY those 6 functions, they are found in sflvault.py
def serial_elgamal_msg(stuff):
    """Get a 2-elements tuple of str(), return a string."""
    ns = b64encode(stuff[0]) + ':' + \
         b64encode(stuff[1])
    return ns

def unserial_elgamal_msg(stuff):
    """Get a string, return a 2-elements tuple of str()"""
    x = stuff.split(':')
    return (b64decode(x[0]),
            b64decode(x[1]))

def serial_elgamal_pubkey(stuff):
    """Get a 3-elements tuple of long(), return a string."""
    ns = b64encode(long_to_bytes(stuff[0])) + ':' + \
         b64encode(long_to_bytes(stuff[1])) + ':' + \
         b64encode(long_to_bytes(stuff[2]))         
    return ns

def unserial_elgamal_pubkey(stuff):
    """Get a string, return a 3-elements tuple of long()"""
    x = stuff.split(':')
    return (bytes_to_long(b64decode(x[0])),
            bytes_to_long(b64decode(x[1])),
            bytes_to_long(b64decode(x[2])))

def serial_elgamal_privkey(stuff):
    """Get a 4-elements tuple of long(), return a string.

    This contains the private (two first elements) and the public key."""
    ns = b64encode(long_to_bytes(stuff[0])) + ':' + \
         b64encode(long_to_bytes(stuff[1])) + ':' + \
         b64encode(long_to_bytes(stuff[2])) + ':' + \
         b64encode(long_to_bytes(stuff[3]))
    return ns

def unserial_elgamal_privkey(stuff):
    """Get a string, return a 4-elements tuple of long()

    This contains the private (two first elements) and the public key."""
    x = stuff.split(':')
    return (bytes_to_long(b64decode(x[0])),
            bytes_to_long(b64decode(x[1])),
            bytes_to_long(b64decode(x[2])),
            bytes_to_long(b64decode(x[3])))


#
# Encryption / decryption stuff
#

#
# Blowfish encrypt for private keys (client only)
#
def encrypt_privkey(something, pw):
    """Encrypt using a password and Blowfish.

    something should normally be 8-bytes padded, but we add some '\0'
    to pad it.

    Most of the time anyway, we get some base64 stuff to encrypt, so
    it shouldn't pose a problem."""
    b = Blowfish.new(pw)
    return b64encode(b.encrypt(something + (((8 - (len(something) % 8)) % 8) * "\x00")))

def decrypt_privkey(something, pw):
    """Decrypt using Blowfish and a password

    Remove padding on right."""
    b = Blowfish.new(pw)
    return b.decrypt(b64decode(something)).rstrip("\x00")


#
# Encrypt / decrypt service's secrets.
#

def encrypt_secret(secret):
    """Gen. a random key, AES256 encrypts the secret, return the random key"""
    seckey = randfunc(32)
    a = AES.new(seckey)
    # Add padding to have a multiple of 16 bytes 
    ciphertext = a.encrypt(secret + (((16 - len(secret) % 16) % 16) * "\x00"))
    ciphertext = b64encode(ciphertext)
    seckey = b64encode(seckey)
    del(a)
    return (seckey, ciphertext)

# DRY: this is copied AS-IS in sflvault.py, please keep in sync, until we
#      have shared libs.
def decrypt_secret(seckey, ciphertext):
    """Decrypt using the provided seckey"""
    a = AES.new(b64decode(seckey))
    ciphertext = b64decode(ciphertext)
    secret = a.decrypt(ciphertext).rstrip("\x00")
    del(a)
    del(ciphertext)
    return secret