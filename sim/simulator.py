from queue import PriorityQueue

import numpy as np

from blitz_protocol import BlitzProtocol
from htlc_protocol import HTLCProtocol
from utils import get_random_element
from constants import FAILED, SUCCESS, GO_IDLE, RELEASING, TX_ER_PUBLISHED, RELEASE_ALL, REVOKING

import copy
import random





class Simulator():

    epoch_size = 400
    percentage_of_failed = 10
    counter_of_operations=0

    def __init__(self, protocol):
        self.protocol = protocol

    '''
        Preforms the simulation of a payment for specific transactions
    Params:
        @transactions -- [Transaction] array of txs to be simulated
    '''
    def simulate_transactions(self, transactions):
        self.transactions = transactions
        # Generate random transactions
        self.txs = copy.copy(transactions)

        while (self.txs):

            if len(type(self.protocol).successfully_reached_receiver_txs)==Simulator.epoch_size:
                #next epoch
                self.go_to_next_epoch()

            
            # Pick a random tx
            tx, index = get_random_element(self.txs)

            # if(Simulator.counter_of_operations==1000):
            #     Simulator.counter_of_operations=0
            #     self.go_to_next_epoch()
            #
            # Simulator.counter_of_operations+=1
            # Perform one execution step of the tx
            self.protocol.continue_tx(tx)

            if tx.status == FAILED or tx.status == SUCCESS or tx.status == GO_IDLE:
                # Tx finished or waiting the end of the epoch
                self.txs.pop(index)

            if len(self.txs)==0:
                if len(type(self.protocol).successfully_reached_receiver_txs)!=0:
                    self.go_to_next_epoch()

    '''
        After 1 epoch all the txs that reached the receiver are either released/all released in HTLC/Blitz case
        or revoked/tx_er_published(all revoked) in HTLC/Blitz
    '''

    def go_to_next_epoch(self):

        #failedTxs = np.random.choice(type(self.protocol).succesfullTxs, size=int(len(type(self.protocol).succesfullTxs) * 0.2), replace=False)

        failedTxs = random.sample(list(type(self.protocol).successfully_reached_receiver_txs),int(len(type(self.protocol).successfully_reached_receiver_txs) * 0.5))
        #add all t.ids in an array
        for t in failedTxs:
            type(self.protocol).all_failedTxs.append(t.id)

        for t in type(self.protocol).successfully_reached_receiver_txs:
            if isinstance(self.protocol, BlitzProtocol):
                if t in failedTxs:
                    t.status = TX_ER_PUBLISHED
                    t.failed_purposely=True
                else:
                    t.status = RELEASE_ALL
            elif isinstance(self.protocol, HTLCProtocol):
                if t in failedTxs:
                    t.status = REVOKING
                    t.failed_purposely = True
                else:
                    t.status=RELEASING

                self.txs.append(t)
            self.protocol.continue_tx(t)
        type(self.protocol).successfully_reached_receiver_txs=[]





