from queue import PriorityQueue

import numpy as np

# from blitz_protocol import BlitzProtocol
# from htlc_protocol import HTLCProtocol
# from run_simulator import get_random_element
from constants import FAILED, SUCCESS, GO_IDLE, RELEASING, TX_ER_PUBLISHED, RELEASE_ALL, REVOKING, TX_ER_CHECKING, \
    REVOKE_ALL

import copy
import random
import array


# from sim.transactions import Transaction


class Simulator():
    failed_Blitz = []
    failed_HTLC = []
    array_rounds = []

    # stateSet = True --unnecessary

    def __init__(self, protocol, epoch_size):
        self.protocol = protocol
        self.epoch_size = epoch_size
        self.round_counter = 0


    '''
        Preforms the simulation of a payment for specific transactions
    Params:
        @transactions -- [Transaction] array of txs to be simulated
    '''

    def simulate_transactions(self, transactions):
        np.random.seed(0)
        self.transactions = transactions

        # Generate random transactions
        self.txs = []
        self.txs_cleaning = copy.copy(transactions)

        # First get rid of all the transactions which lead to canonical error
        for tx in self.txs_cleaning:
            if tx.find_path():
                is_processable = True
                for dchannel in tx.dchannels_path:
                    if (dchannel.balance < tx.payment_amount or  # according to topology the balance is not enough
                            dchannel.min_htlc > tx.payment_amount
                            # according to topology the payment amount is below the minimum
                    ):
                        is_processable = False
                        break
                if is_processable:
                    self.txs.append(tx)
        # hits=0
        # for tx in self.txs:
        #     for tx2 in self.txs:
        #         if tx.id != tx2.id:
        #             for dchannel in tx.dchannels_path:
        #                 for dchannel2 in tx2.dchannels_path:
        #                     if dchannel.src.pk== dchannel2.src.pk and dchannel.trg.pk== dchannel2.trg.pk:
        #                         hits+=1
        #
        # print("HITS")
        # print(hits)
        self.array_rounds=[]
        for i in range(0, 1000000):
            self.array_rounds.append([])


        for tx in self.txs:
            position = np.random.randint(0, 5000)
            self.array_rounds[position].append(tx)

        for i, round in enumerate(self.array_rounds):
            for j in range(len(round)):
                tx = round[j]
                # process next tx in the row
                if tx.status != FAILED and tx.status != SUCCESS:
                    self.protocol.continue_tx(tx, self.round_counter, self.epoch_size)
                    self.round_counter += 1

                if tx.status == REVOKE_ALL:
                    self.protocol.continue_tx(tx, self.round_counter, self.epoch_size)

                # if the TX_ER_CHECKING is set process it right away
                if tx.status == TX_ER_CHECKING:
                    self.protocol.continue_tx(tx, self.round_counter, self.epoch_size)

                if tx.status == GO_IDLE:
                    self.protocol.continue_tx(tx, self.round_counter, self.epoch_size)
                    # release all channels immediately in this round
                    if tx.status == RELEASE_ALL or tx.status == TX_ER_PUBLISHED:
                        self.protocol.continue_tx(tx, self.round_counter, self.epoch_size)
                    # put tx further away and then revoke all channels
                    # if tx.status == TX_ER_PUBLISHED:
                    #     self.array_rounds[i + self.delay_param].append(tx)
                    # distribute tx over delay_in_operations in an array
                    if tx.status == REVOKING:
                        for step in range(len(tx.dchannels_path)):
                            self.array_rounds[int(i + self.epoch_size * (step + 1))].append(tx)

                if tx.status != FAILED and tx.status != SUCCESS and tx.status != REVOKING and tx.status != TX_ER_PUBLISHED:
                    self.array_rounds[i + 1].append(tx)

        old = False
        if (old):
            # Process all the txs that according to the topology could be processed
            while (True):

                # check if all txs are processed until the end
                all_done = True
                done_counter = 0
                idle_counter = 0
                for tx in self.txs:
                    if tx.status != SUCCESS and tx.status != FAILED:
                        if tx.status == GO_IDLE:
                            idle_counter += 1
                        all_done = False
                    else:
                        done_counter += 1

                if all_done:
                    print(done_counter)
                    break

                if self.round_counter % 1000 == 0:
                    print(done_counter)
                    print(self.round_counter)

                percentage_of_done = done_counter / len(self.txs)
                if percentage_of_done > 0.9:
                    print(done_counter)
                    break
                #     for tx in type(self.protocol).successfully_reached_receiver_txs:
                #         if tx.status!= FAILED and tx.status!=SUCCESS:
                #             self.protocol.continue_tx(tx, self.round_counter, self.delay_param )

                # check if it is time for the next epoch
                # if len(type(self.protocol).successfully_reached_receiver_txs) == self.delay_param:
                #     # next epoch
                #     self.go_to_next_epoch()

                # if Simulator.round_counter%self.delay_param==0:
                #     self.go_to_next_epoch()
                # print(done_counter)
                # if there is no more txs to process do the last epoch and release all locked channels------------------------
                # if (len(self.txs) - done_counter-len(Simulator.failed_HTLC)-len(Simulator.failed_Blitz)) == idle_counter:
                #     self.go_to_next_epoch()
                #     while len(Simulator.failed_HTLC) != 0 or len(Simulator.failed_Blitz) != 0:
                #         self.process_failed_tx_form_the_last_epoch()

                # ------------------------------------------------------------------------------------------------------------

                # Pick a random tx
                r = np.random.randint(0, len(self.txs))
                tx = self.txs[r]

                # tx, index = self.get_random_element(self.txs)

                # if(Simulator.counter_of_operations==1000):
                #     Simulator.counter_of_operations=0
                #     self.go_to_next_epoch()
                #
                # Simulator.counter_of_operations+=1
                # Perform one execution step of the tx

                if tx.status != FAILED and tx.status != SUCCESS and tx.failed_purposely == False:
                    self.protocol.continue_tx(tx, self.round_counter, self.epoch_size)
                    self.round_counter += 1

                # if the TX_ER_CHECKING is set process it right away
                if tx.status == TX_ER_CHECKING:
                    self.protocol.continue_tx(tx, self.round_counter, self.epoch_size)

                if tx.status == GO_IDLE:
                    self.protocol.continue_tx(tx, self.round_counter, self.epoch_size)
                    if tx.status == TX_ER_PUBLISHED or tx.status == RELEASE_ALL or tx.status == REVOKING:
                        self.protocol.continue_tx(tx, self.round_counter, self.epoch_size)

                # if tx.status == FAILED or tx.status == SUCCESS or tx.status == GO_IDLE:
                #     # Tx finished or waiting the end of the epoch
                #     self.txs.pop(index)

    '''
        After 1 epoch all the txs that reached the receiver are either all released in HTLC/Blitz case
        or revoked(only the last channel)/tx_er_published(all revoked) in HTLC/Blitz
    '''

    # def go_to_next_epoch(self):
    #     self.process_failed_tx_form_the_last_epoch()
    #
    #     # failedTxs = np.random.choice(type(self.protocol).succesfullTxs, size=int(len(type(self.protocol).succesfullTxs) * 0.2), replace=False)
    #     failedTxs = random.sample(list(type(self.protocol).successfully_reached_receiver_txs),
    #                               int(len(type(
    #                                   self.protocol).successfully_reached_receiver_txs) * self.percentage_of_failed))
    #
    #     # add all t.ids in an array
    #     for t in failedTxs:
    #         type(self.protocol).all_failedTxs.append(t.id)
    #         type(self.protocol).failed_purposely.append(t)
    #
    #     for t in type(self.protocol).successfully_reached_receiver_txs:
    #         if isinstance(self.protocol, BlitzProtocol):
    #             if t in failedTxs:
    #                 t.status = TX_ER_PUBLISHED
    #                 t.failed_purposely = True
    #                 self.protocol.continue_tx(t)
    #                 # imulator.failed_Blitz.append(t)
    #             else:
    #                 t.status = RELEASE_ALL
    #                 self.protocol.continue_tx(t)
    #         elif isinstance(self.protocol, HTLCProtocol):
    #             if t in failedTxs:
    #                 t.status = REVOKING
    #                 t.failed_purposely = True
    #                 Simulator.failed_HTLC.append(t)
    #             else:
    #                 t.status = RELEASE_ALL  # this has to be done immediately
    #                 self.protocol.continue_tx(t)
    #
    #     type(self.protocol).successfully_reached_receiver_txs = []
    #
    # '''
    #     All txs that are purposely failed in all epochs until now are processed.
    # '''
    #
    # def process_failed_tx_form_the_last_epoch(self):
    #     temp_failed = []
    #     if isinstance(self.protocol, BlitzProtocol):
    #         for t in Simulator.failed_Blitz:
    #             self.protocol.continue_tx(t)
    #             assert t.status == FAILED
    #             if t.status != FAILED:
    #                 temp_failed.append(t)
    #
    #         Simulator.failed_Blitz = []
    #         Simulator.failed_Blitz = copy.copy(temp_failed)
    #
    #         temp_failed = []
    #
    #     if isinstance(self.protocol, HTLCProtocol):
    #         for t in Simulator.failed_HTLC:
    #             self.protocol.continue_tx(t)
    #             if t.status != FAILED:
    #                 temp_failed.append(t)
    #
    #         Simulator.failed_HTLC = []
    #         Simulator.failed_HTLC = copy.copy(temp_failed)
    #
    #         temp_failed = []

    '''
        Gets a random element from the elem_list
    '''

    def get_random_element(self, elem_list):
        if Simulator.stateSet == False:
            random.setstate(self.state)
            Simulator.stateSet = True
        r = random.randint(0, len(elem_list) - 1)
        print(r)
        return elem_list[r], r
