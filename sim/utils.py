import json
import random
import string
import hashlib

import copy

from crypto_utils import generate_key_pair,sign,verify
from transactions import Transaction

'''
    Function that loads json file
'''
def load_json_file(file_name):
    with open(file_name) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("JSONDecodeError: " + file_name)
    return data



'''
    Function that generates pk and sk for every node on the path
    @tx -- [Transaction] specific tx
'''
def generate_keys_for_nodes(tx):
    for dchannel in tx.dchannels_path:
        if not dchannel.src.fict_private_key: #should be checking also dchannel.src.fict_public_key
            privk, pubk = generate_key_pair()
            assert(privk is not None and pubk is not None)
            #print("generated key pair")
            dchannel.src.fict_private_key = privk
            dchannel.src.fict_public_key = pubk

        if not dchannel.trg.fict_private_key:
            privk, pubk = generate_key_pair()
            assert(privk is not None and pubk is not None)
            #print("generated key pair")
            dchannel.trg.fict_private_key = privk
            dchannel.trg.fict_public_key = pubk

'''
    Function for calculating total_fee of each edge
Params:
    @df -- [pd.df] dataframe w/ attributes of directed edges
    @amount -- [int] upper bound of the tx amount 
Returns:
    @total_fee -- [float] total_fee for respective edge
'''
def calculate_tx_fee( df, amount):
    return (df["fee_base_msat"]/1000.0)+ amount* df["fee_rate_milli_msat"] / 10.0 ** 6


'''
    Function for calculating routing weight in given graph
Params:
    @df -- [pd.df] dataframe w/ attributes of directed edges
    @amount -- [int] upper bound of the tx amount 
Returns:
    @routing_weight -- [float] measure that indicates the cost of tx being routed through respective edge(it will be needed for the shortest path algorithm)
'''
def calculate_routing_weight(df,amount):
    return (df["total_fee"] + amount * df["time_lock_delta"] * df["risk_factor"] / 5259600)



def simulate_state_agreement(dchannel):
    # Implement the simulation of signature exchage:

    # Create a random msg
    msg = get_random_string(100).encode('ascii')
    msg = hashlib.sha256(msg).hexdigest()

    secret_key = dchannel.src.fict_private_key
    public_key = dchannel.src.fict_public_key
    # src signs the tx
    signature = sign(secret_key, msg)

    # verify signature
    verify(public_key, msg, signature)

    # Create a random msg
    msg2 = get_random_string(100).encode('ascii')
    msg2 = hashlib.sha256(msg2).hexdigest()
    secret_key2 = dchannel.trg.fict_private_key
    public_key2 = dchannel.trg.fict_public_key
    # node 2 signs the tx
    signature2 = sign(secret_key2, msg2)

    # verify signature
    verify(public_key2, msg2, signature2)

'''
    Gets a random element from the elem_list
'''
def get_random_element(elem_list):
    r = random.randint(0, len(elem_list) - 1)
    return elem_list[r], r


def get_random_string(length):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str

'''
    Generates tx_er data structure [Dict] that is used for enabling refund 
    if the transaction doesn't fulfill conditions
     -- it can be set on private mode: id is a random bitstring
     -- or non-private mode: id is the pk of the sender 
'''
def generate_tx_er(tx:Transaction):
    random_stealth_addresses=[]
    for _ in range(len(tx.dchannels_path)):
        random_stealth_addresses.append(get_random_string(12))
    tx_er={
        "id":tx.src.pk,
        "epsilon":0.001 ,  #some predefined small amount
        "published" :False,
        "rList" :random_stealth_addresses
    }
    return tx_er

'''
    Creates a preimage for the txs in htlc protocol
'''

def create_preimage(tx):
    return str(tx.id) + tx.src.pk[:4] + tx.trg.pk[:4]
'''
    Creates a hash value of the data structure tx_er [Dict] that is unique for every tx
'''
def create_hash(tx_er):
    m = hashlib.sha256()
    m.update(tx_er.encode())
    pi_hash = m.hexdigest()
    return pi_hash[:10]



def make_hash(o):

  """
  Makes a hash from a dictionary, list, tuple or set to any level, that contains
  only other hashable types (including any lists, tuples, sets, and
  dictionaries).
  """

  if isinstance(o, (set, tuple, list)):

    return tuple([make_hash(e) for e in o])

  elif not isinstance(o, dict):

    return hash(o)

  new_o = copy.deepcopy(o)
  for k, v in new_o.items():
    new_o[k] = make_hash(v)

  return hash(tuple(frozenset(sorted(new_o.items()))))