# -*- coding: utf-8 -*-
#
#  Copyright 2011 Sybren A. Stüvel <sybren@stuvel.eu>
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

'''Commandline scripts.

These scripts are called by the executables defined in setup.py.
'''

import abc
import sys
from optparse import OptionParser

import rsa
import rsa.bigfile

def keygen():
    '''Key generator.'''

    # Parse the CLI options
    parser = OptionParser(usage='usage: %prog [options] keysize',
            description='Generates a new RSA keypair of "keysize" bits.')
    
    parser.add_option('--pubout', type='string',
            help='Output filename for the public key. The public key is '
            'not saved if this option is not present. You can use '
            'pyrsa-priv2pub to create the public key file later.')
    
    parser.add_option('--privout', type='string',
            help='Output filename for the private key. The key is '
            'written to stdout if this option is not present.')

    parser.add_option('--form',
            help='key format of the private and public keys - default PEM',
            choices=('PEM', 'DER'), default='PEM')

    (cli, cli_args) = parser.parse_args(sys.argv[1:])

    if len(cli_args) != 1:
        parser.print_help()
        raise SystemExit(1)
    
    try:
        keysize = int(cli_args[0])
    except ValueError:
        parser.print_help()
        print >>sys.stderr, 'Not a valid number: %s' % cli_args[0]
        raise SystemExit(1)

    print >>sys.stderr, 'Generating %i-bit key' % keysize
    (pub_key, priv_key) = rsa.newkeys(keysize)


    # Save public key
    if cli.pubout:
        print >>sys.stderr, 'Writing public key to %s' % cli.pubout
        data = pub_key.save_pkcs1(format=cli.form)
        with open(cli.pubout, 'w') as outfile:
            outfile.write(data)

    # Save private key
    data = priv_key.save_pkcs1(format=cli.form)
    
    if cli.privout:
        print >>sys.stderr, 'Writing private key to %s' % cli.privout
        with open(cli.privout, 'w') as outfile:
            outfile.write(data)
    else:
        print >>sys.stderr, 'Writing private key to stdout'
        sys.stdout.write(data)


class CryptoOperation(object):
    '''CLI callable that operates with input, output, and a key.'''

    __metaclass__ = abc.ABCMeta

    keyname = 'public' # or 'private'
    usage = 'usage: %%prog [options] %(keyname)s_key'
    description = None
    operation = 'decrypt'
    operation_past = 'decrypted'
    operation_progressive = 'decrypting'
    input_help = 'Name of the file to %(operation)s. Reads from stdin if ' \
            'not specified.'
    output_help = 'Name of the file to write the %(operation_past)s file ' \
            'to. Written to stdout if this option is not present.'

    key_class = rsa.PublicKey

    def __init__(self):
        self.usage = self.usage % self.__class__.__dict__
        self.input_help = self.input_help % self.__class__.__dict__
        self.output_help = self.output_help % self.__class__.__dict__

    @abc.abstractmethod
    def perform_operation(self, indata, key):
        '''Performs the program's operation.

        Implement in a subclass.

        :returns: the data to write to the output.
        '''

    def __call__(self):
        '''Runs the program.'''

        (cli, cli_args) = self.parse_cli()

        key = self.read_key(cli_args[0], cli.keyform)

        indata = self.read_infile(cli.input)

        print >>sys.stderr, self.operation_progressive.title()
        outdata = self.perform_operation(indata, key)

        self.write_outfile(outdata, cli.output)

    def parse_cli(self):
        '''Parse the CLI options
        
        :returns: (cli_opts, cli_args)
        '''

        parser = OptionParser(usage='usage: %prog [options] public_key',
                description='Encrypts a file. The file must be shorter than the '
                'key length in order to be encrypted. For larger files, use the '
                'pyrsa-encrypt-bigfile command.')
        
        parser.add_option('--input', type='string',
                help='Name of the file to encrypt. Reads from stdin if '
                     'not specified.')

        parser.add_option('--output', type='string',
                help='Name of the file to write the encrypted file to. '
                     'Written to stdout if this option is not present.')

        parser.add_option('--keyform',
                help='Key format of the key - default PEM',
                choices=('PEM', 'DER'), default='PEM')

        (cli, cli_args) = parser.parse_args(sys.argv[1:])

        if len(cli_args) != 1:
            parser.print_help()
            raise SystemExit(1)

        return (cli, cli_args)

    def read_key(self, filename, keyform):
        '''Reads a public or private key.'''

        print >>sys.stderr, 'Reading %s key from %s' % (self.keyname, filename)
        with open(filename) as keyfile:
            keydata = keyfile.read()

        return self.key_class.load_pkcs1(keydata, keyform)
    
    def read_infile(self, inname):
        '''Read the input file'''

        if inname:
            print >>sys.stderr, 'Reading input from %s' % inname
            with open(inname, 'rb') as infile:
                return infile.read()

        print >>sys.stderr, 'Reading input from stdin'
        return sys.stdin.read()

    def write_outfile(self, outdata, outname):
        '''Write the output file'''

        if outname:
            print >>sys.stderr, 'Writing output to %s' % outname
            with open(outname, 'wb') as outfile:
                outfile.write(outdata)
        else:
            print >>sys.stderr, 'Writing output to stdout'
            sys.stdout.write(outdata)

class EncryptOperation(CryptoOperation):
    '''Encrypts a file.'''

    keyname = 'public'
    description = ('Encrypts a file. The file must be shorter than the key '
            'length in order to be encrypted. For larger files, use the '
            'pyrsa-encrypt-bigfile command.')
    operation = 'encrypt'
    operation_past = 'encrypted'
    operation_progressive = 'encrypting'


    def perform_operation(self, indata, pub_key):
        '''Encrypts files.'''

        return rsa.encrypt(indata, pub_key)

class DecryptOperation(CryptoOperation):
    '''Decrypts a file.'''

    keyname = 'private'
    description = ('Decrypts a file. The original file must be shorter than '
            'the key length in order to have been encrypted. For larger '
            'files, use the pyrsa-decrypt-bigfile command.')
    operation = 'decrypt'
    operation_past = 'decrypted'
    operation_progressive = 'decrypting'
    key_class = rsa.PrivateKey

    def perform_operation(self, indata, priv_key):
        '''Decrypts files.'''

        return rsa.decrypt(indata, priv_key)

encrypt = EncryptOperation()
decrypt = DecryptOperation()

