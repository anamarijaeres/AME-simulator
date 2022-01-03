from constants import FAILED, SUCCESS, SETUP_DONE, REVOKING, RELEASING, FORWARDING, NOT_STARTED, LOCKED, RELEASED, \
    REVOKED, TX_ER_CHCEKING, TX_ER_PUBLISHED, INSTANT_REVOKING
from transactions import Transaction

from utils import generate_keys_for_nodes


class Protocol():


    '''
    @network
    @contract_class --depending on protocol eg. (HTLCContract, BlitzContract)
    '''

    def __init__(self, network, contract_class=None):
        self.network = network
        self.contract_class = contract_class

    '''
        Setup phase of the protocol,generates pk and sk for every node on the path
    Params:
        @tx -- transaction
    '''

    def setup(self, tx):
        generate_keys_for_nodes(tx)

    '''
        Creates the first contract in the channel from sender to the first intermediary
    Params:
        @tx -- [Transaction]
        @next_channel -- [DirectedChannel] src.pk=sender trg.pk=first intermediary
    '''

    def create_first_contract(self, tx, next_channel):
        return self.contract_class.new_contract(tx, next_channel)

    '''
        Creates the contract referring to the previous contract -- in Blitz txer is used
    Params:
        @prev_contract -- [Contract]
        @next_channel -- [DirectedChannel] src.pk=prev_contract.dchannel.trg.pk/ next_channel.src.pk 
    '''

    def create_next_contract(self, prev_contract, next_dchannel):
        return self.contract_class.get_next_contract(prev_contract, next_dchannel)

    '''
        Forwards the contract if the contract passes the check, then it locks it and 
        puts it into pending_contracts[] for this tx
    '''

    def forward_contract(self, tx, contract):
        if contract.check(tx):
            contract.lock()
            tx.pending_contracts.insert(0, contract)
            return True
        return False

    # def continue_tx(self, tx:Transaction):
    #     status = tx.status
    #     if status == NOT_STARTED:
    #         if not tx.find_path():
    #             tx.status = FAILED
    #             return
    #         self.setup(tx)
    #         tx.status = SETUP_DONE
    #
    #     elif status == SETUP_DONE:
    #         dchannel = tx.get_next_dchannel()
    #         contract = self.create_first_contract(tx, dchannel)
    #         if self.forward_contract(tx, contract):
    #             tx.status = FORWARDING
    #         else:
    #             tx.status = FAILED
    #
    #     elif status == FORWARDING:
    #         dchannel = tx.get_next_dchannel()
    #         if dchannel is None:
    #             tx.status = TX_ER_CHCEKING
    #         else:
    #             prev_contract = tx.pending_contracts[0]
    #             new_contract = self.create_next_contract(prev_contract, dchannel)
    #             if not self.forward_contract(tx, new_contract):
    #                 tx.status = REVOKING
    #
    #     elif status==TX_ER_CHCEKING:
    #         contractWithSender = tx.get_first_pending_contract() #i have to implement new function which gets the first contract(one sent from sender)
    #         contractWithReciever=tx.get_last_pending_contract()
    #         assert contractWithSender is not None
    #         if contractWithSender is not None:
    #             if not contractWithSender.tx_er_check(contractWithReciever):
    #                 print("Tx_er has been tampered.")
    #                 #tx_er need to be published
    #                 tx.status==TX_ER_PUBLISHED
    #             else:
    #                 print("Tx_er OK! Starting the release phase")
    #                 tx.status=RELEASING
    #
    #     elif status == RELEASING:
    #         contract = tx.get_first_pending_contract() #this is fast track Blitz
    #         if contract is not None:
    #             if not contract.release():
    #                 print("RELEASE ERROR")
    #         else:
    #             tx.status = SUCCESS
    #
    #     elif status == TX_ER_PUBLISHED:
    #         if tx.publish_tx_er():
    #             print("Tx_er published")
    #             tx.status=INSTANT_REVOKING
    #         else:
    #             print("TX_ER publishing error")
    #
    #     elif status==INSTANT_REVOKING:
    #         if tx.instantly_revoke():
    #             print("Everybody revoked")
    #             tx.status = FAILED
    #         else:
    #             print("Error while doing the instant revoke.")
    #
    #     elif status == REVOKING:   #honest revoking without tx_er being published
    #         contract = tx.get_last_pending_contract()
    #         if contract is not None:
    #             contract.revoke()
    #         else:
    #             tx.status = FAILED


class Contract:
    '''
    @tx -- [Transaction] making of contract for this tx
    @dhcannel   [DirectedChannel] the channel with which this contract is bound to
    '''

    def __init__(self, tx, dchannel):
        self.tx = tx
        self.dchannel = dchannel
        self.payment_amount = None
        self.status = None

    '''
        Checks whether this directed channel can process the payment -- checking only balance
    '''

    def check(self):
        if self.dchannel.balance < self.payment_amount:
            return False
        return True

    @classmethod
    def new_contract(cls, tx, next_dchannel):
        contract = cls(tx, next_dchannel)
        contract.payment_amount = tx.payment_amount + tx.total_amount_fees
        return contract

    @classmethod
    def get_next_contract(cls, prev_contract, next_dchannel):
        contract = cls(prev_contract, next_dchannel)
        contract.payment_amount = prev_contract.payment_amount - next_dchannel.get_fee()
        return contract

    '''
        Locks the payment amount in the channel using the attribute locked_balance
    '''

    def lock(self):
        assert self.dchannel is not None
        self.dchannel.balance -= self.payment_amount
        self.dchannel.locked_balance += self.payment_amount
        self.status = "LOCKED"
        self.save_data()

    def release(self):
        assert self.dchannel is not None
        assert self.status == "LOCKED"
        self.dchannel.locked_balance -= self.payment_amount
        brother_channel = self.dchannel.get_brother_channel()
        brother_channel.balance += self.payment_amount
        self.status = "RELEASED"
        self.save_data()
        return True

    def revoke(self):
        assert self.dchannel is not None
        self.dchannel.balance += self.payment_amount
        self.dchannel.locked_balance -= self.payment_amount
        self.status = "REVOKED"
        self.save_data()

    def save_data(self):
        contract_record = [
            self.tx.id,
            self.dchannel.src.pk,
            self.dchannel.trg.pk,
            self.status,
            self.payment_amount
        ]
        print(contract_record)

        self.dchannel.channel.data.append(tuple(contract_record))
