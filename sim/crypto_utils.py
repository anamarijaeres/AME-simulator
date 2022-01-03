from ecdsa import SigningKey
#to be modified if we will be concerned with the securtity of protocols

'''
    Generates a signing key, verifing key pair
'''
def generate_key_pair():
    sk = SigningKey.generate() # uses NIST192p
    vk = sk.verifying_key
    return sk, vk

'''
        Function that signs the given message w/ the signing key sk  after encoding it.
    Params:
        @sk -- [?] signing key
        @msg -- [Object]
'''
def sign(sk, msg):
    signature = sk.sign(msg.encode('ascii'))
    return signature

'''
        Function that checks if the signature for the given message is valid
    Params:
        @vk -- [?] verifying key
        @msg -- [Object] signed message
        @signature
'''
def verify(vk, msg, signature):
    if vk.verify(signature, msg.encode('ascii')):
        return True
    return False