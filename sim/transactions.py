import random
import networkx as nx
import numpy as np

#from network_topology import NetworkTopology
from constants import  NOT_STARTED
import copy

class Transaction:

    tx_counter = 0

    def __init__(self, network, src, trg, payment_amount):
        self.id = Transaction.tx_counter
        Transaction.tx_counter += 1

        self.status = NOT_STARTED
        self.network = network
        self.src = src
        self.trg = trg
        self.payment_amount = payment_amount

        self.dchannels_path = []
        self.pending_contracts = []
        self.total_amount_fees = 0
        self.curr_dchannel_index = 0
        self.curr_contract_index = 0
        self.curr_contract_index_fromTheBack=0
        self.tx_er=None
        self.failed_purposely=False
        self.failed_bcs_of_locked_balance_blitz=False
        self.failed_bcs_of_locked_balance_on_Failedtxs_blitz= False
        self.failed_bcs_of_locked_balance_htlc = False
        self.failed_bcs_of_locked_balance_on_Failedtxs_htlc = False

    '''
        Gets the next channel for processing the tx
    '''
    def get_next_dchannel(self):
        if self.curr_dchannel_index >= len(self.dchannels_path):
            return None
        dchannel = self.dchannels_path[self.curr_dchannel_index]
        self.curr_dchannel_index += 1
        return dchannel

    '''
        Gets the contracts according to the LIFO principle
    '''
    def get_last_pending_contract(self):
        if self.curr_contract_index >= len(self.pending_contracts):
            return None
        contract = self.pending_contracts[self.curr_contract_index]
        self.curr_contract_index += 1
        return contract
    '''
        Gets the contracts according to the FIFO principle
    '''
    def get_first_pending_contract(self):
        if self.curr_contract_index_fromTheBack <0:
            return None
        contract = self.pending_contracts[self.curr_contract_index_fromTheBack]
        self.curr_contract_index_fromTheBack -= 1
        return contract

    '''
        Calculates total fees excluding the sender
    '''
    def calculate_total_fees(self):
        if self.dchannels_path:
            for idx,dc in enumerate(self.dchannels_path):
                if idx==0: continue
                self.total_amount_fees += dc.calculate_fee(self.payment_amount)

    '''
        Finds the shortest path and stores it into self.channels_path array
    '''
    def find_path(self):
        self.dchannels_path = []
        g = self.network.get_graph()


        try:
            # sometimes it cannot find a path between src and target (why?)
            nodes_path = nx.shortest_path(g, source=self.src.pk, target=self.trg.pk, weight="routing_weight")
        except:
            return False

        current_src_pk = self.src.pk

        for trg_pk in nodes_path[1:]:
            channel = self.network.get_directed_channel(current_src_pk, trg_pk)
            if channel is not None:
                self.dchannels_path.append(channel)
            else:
                print("ERROR!")
            current_src_pk = trg_pk

        self.curr_contract_index_fromTheBack=len(self.dchannels_path)-1
        self.calculate_total_fees()
        return True
    '''
        Sets the field 'published' in tx_er in every contract to true. Now everybody can refund.
    '''
    def publish_tx_er(self):
        for contract in self.pending_contracts:
            contract.tx_er['published']=True    #should this also be a marked event that node sees or is it enough that it will be seen as the revoke is done
        return True
    '''
        Revokes every contract in the pending_contracts field -- this should be done randomly implement this
    '''
    def instantly_revoke(self):
        for contract in self.pending_contracts:
            contract.revoke()
        return True
    '''
        Releases all the transactions immediately.
    '''

    def release_all(self):
        for contract in self.pending_contracts:
            contract.release()
        return True


class TransactionGenerator:
    '''
    @network -- [NetworkTopology] contains nodes_map & channels_map
    '''
    def __init__(self, networkBlitz,networkHtlc):
        self.networkBlitz = networkBlitz
        self.networkHtlc=networkHtlc

    '''
        Function generates certain number of tx with the respective amount
    Params:
        @number_txs -- number of tx to generate
        @payment_amount -- upper bound OR the exact payment amount
    '''
    def generate(self, number_txs, payment_amount, one_amount_for_all_txs):
        sources = np.random.choice(list(self.networkBlitz.nodes_map.values()), size=number_txs)

        txsBlitz = []
        txsHTLC=[]

        for src in sources:
            srcHtlc= self.networkHtlc.nodes_map.get(src.pk)
            trg = random.sample(list(self.networkBlitz.nodes_map.values()), 1)[0]
            trgHtlc=self.networkHtlc.nodes_map.get(trg.pk)
            while trg == src:
                trg = random.sample(list(self.networkBlitz.nodes_map.values()), 1)[0]
                trgHtlc = self.networkHtlc.nodes_map.get(trg.pk)
            txsBlitz.append((src, trg))
            txsHTLC.append((srcHtlc,trgHtlc))

        transactions = []
        transactions_htlc=[]
        for src, trg in txsBlitz:
            if one_amount_for_all_txs:
                transactions.append(Transaction(self.networkBlitz, src, trg, payment_amount))
            else:
                amt=random.randint(0,payment_amount)
                transactions.append(Transaction(self.networkBlitz, src, trg, amt))

        Transaction.tx_counter =0
        for src,trg in txsHTLC:
            if one_amount_for_all_txs:
                transactions_htlc.append(Transaction(self.networkHtlc, src, trg, payment_amount))
            else:
                amt=random.randint(0,payment_amount)
                transactions_htlc.append(Transaction(self.networkHtlc, src, trg, amt))

        return transactions,transactions_htlc