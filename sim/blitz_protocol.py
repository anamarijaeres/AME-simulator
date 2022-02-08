
from network_topology import DirectedChannel
from protocol import Protocol, Contract

from utils import generate_keys_for_nodes, simulate_state_agreement, generate_tx_er, create_hash, make_hash
from constants import FAILED, SUCCESS, SETUP_DONE, REVOKING, RELEASING, FORWARDING, NOT_STARTED, LOCKED, RELEASED, \
    REVOKED, TX_ER_CHECKING, TX_ER_PUBLISHED, INSTANT_REVOKING, GO_IDLE, FORCING_REVOKE, RELEASE_ALL

# this should be changed accordingly
TIMELOCK = 10000
TIMELOCK_DELTA = 1000


class BlitzProtocol(Protocol):
    version = ""
    force_revoke_enabled = False

    successfully_reached_receiver_txs = []
    successfully_reached_receiver_counter = 0

    all_failedTxs = []
    failed_purposely = []

    final_failure = []
    inflight_failure = []
    collateral_failure = []

    '''
    @network -- [NetworkTopology]
    @contract_class -- depending on protocol eg. (HTLCContract, BlitzContract)
    @version -- SimpleBlitz or FastBlitz
    @force_revoke_enabled -- [boolean]
    '''

    def __init__(self, network, contract_class, version, force_revoke_enabled):
        super().__init__(network, contract_class)
        BlitzProtocol.version = version
        BlitzProtocol.force_revoke_enabled = force_revoke_enabled

    '''
        Setup phase of the protocol,generates pk and sk for every node on the path and unique tx_er for the given tx
    Params:
        @tx -- transaction
    '''

    def setup(self, tx):
        generate_keys_for_nodes(tx)
        tx.tx_er = generate_tx_er(tx)


    '''
        Continues tx according to the current tx.status
    '''

    def continue_tx(self, tx, round_counter,epoch_size):
        status = tx.status
        if status == NOT_STARTED:
            # if not tx.find_path():
            #     tx.status = FAILED
            #     return
            self.setup(tx)
            tx.status = SETUP_DONE

        elif status == SETUP_DONE:
            dchannel = tx.get_next_dchannel()
            contract = self.create_first_contract(tx, dchannel)
            if self.forward_contract(tx, contract):
                tx.status = FORWARDING
            else:
                tx.status = FAILED

        elif status == FORWARDING:
            dchannel = tx.get_next_dchannel()
            if dchannel is None:
                tx.status = TX_ER_CHECKING
            else:
                prev_contract = tx.pending_contracts[0]
                new_contract = self.create_next_contract(prev_contract, dchannel)
                if not self.forward_contract(tx, new_contract):
                    tx.status = REVOKING

        elif status == TX_ER_CHECKING:
            contractWithSender = tx.get_first_pending_contract()  # FIFO -- first in first out
            contractWithReciever = tx.get_last_pending_contract()  # LIFO -- last in first out
            assert contractWithSender is not None
            if contractWithSender is not None:
                if not contractWithSender.tx_er_check(contractWithReciever):
                    print("Tx_er has been tampered.")
                    # tx_er needs to be published
                    tx.status == TX_ER_PUBLISHED
                else:
                    #print("Tx_er OK! Starting the release phase")
                    if BlitzProtocol.force_revoke_enabled == False:
                        if BlitzProtocol.version == "FastBlitz":
                            tx.status = RELEASING
                        if BlitzProtocol.version == "SimpleBlitz":
                            BlitzProtocol.successfully_reached_receiver_txs.append(tx)
                            BlitzProtocol.successfully_reached_receiver_counter += 1
                            tx.status = GO_IDLE
                    else:  # the payment will fail due to force_revoke
                        tx.status = TX_ER_PUBLISHED



        elif status == RELEASING:
            contract = tx.get_first_pending_contract()  # this is fast track Blitz
            if contract is not None:
                if not contract.release():
                    print("RELEASE ERROR")
            else:
                tx.status = SUCCESS

        #here  i have to set delay for all channels
        elif status == GO_IDLE:
            if tx.premarked_as_failed == True:
                tx.set_delays_blitz(round_counter,epoch_size)
                tx.status = TX_ER_PUBLISHED
            else:
                tx.status=RELEASE_ALL
            return

        elif status == RELEASE_ALL:
            if tx.release_all():
                #print("Everybody released.")
                tx.status = SUCCESS
            else:
                print("RELEASE_ALL ERROR")

        elif status == TX_ER_PUBLISHED:  # should this be separated from instant_revoking or is that an atomic action
            for delay in tx.delays_blitz:
                if delay > round_counter:
                    return
            if tx.publish_tx_er():
                #print("Tx_er published")
                if tx.instantly_revoke():
                    #print("Everybody revoked")
                    tx.status = FAILED
                else:
                    print("Error while doing the instant revoke.")
            else:
                print("TX_ER publishing error")


        elif status == REVOKING:  # honest revoking without tx_er being published
            contract = tx.get_last_pending_contract()
            if contract is not None:
                contract.revoke()
            else:
                tx.status = FAILED


class BlitzContract(Contract):

    def __init__(self, tx, dchannel: DirectedChannel):
        self.tx = tx
        self.dchannel = dchannel
        self.payment_amount = None
        self.status = None
        self.timelock = TIMELOCK
        self.tx_er = None  # data structure with attributes id, epsilon, published and rList
        self.tx_er_hash = None
        # generate new state TX state =genState( alfa , timelock , channel)
        # generate TX r =genRef( TX state, theta)

    @classmethod
    def new_contract(cls, tx, next_dchannel: DirectedChannel):
        contract = cls(tx, next_dchannel)
        contract.payment_amount = tx.payment_amount + tx.total_amount_fees
        contract.tx_er = tx.tx_er  # instead of cash here is txer
        # should i use the built in hash function or create_hash
        contract.tx_er_hash = make_hash(contract.tx_er)
        return contract

    @classmethod
    def get_next_contract(cls, prev_contract, next_dchannel):
        contract = cls(prev_contract.tx, next_dchannel)
        contract.payment_amount = prev_contract.payment_amount - next_dchannel.calculate_fee(
            prev_contract.tx.payment_amount)
        contract.timelock = prev_contract.timelock
        contract.tx_er = prev_contract.tx_er  # here it is txer
        contract.tx_er_hash = make_hash(contract.tx_er)
        return contract

    '''
        Checks if the the next directed channel fulfills the conditions for forwarding the payment
    '''

    def check(self, tx):
        if (
                self.dchannel.balance < self.payment_amount or  # the balance is not enough
                self.dchannel.min_htlc > self.payment_amount  # the payment amount is below the minimum
                #  self.timelock < 0  # i wouldn't put this in blitz just yet
        ):
            # this checks if the failure happened due to the locked coins in the channel or due to purposely failed
            # transactions which locked coins in the channel
            if (
                    self.dchannel.locked_balance + self.dchannel.balance >= self.payment_amount > self.dchannel.min_htlc
            ):
                ind = len(BlitzProtocol.inflight_failure)
                BlitzProtocol.inflight_failure.append(tx)
                tx.inflight_failure_blitz = True

                # data is an array:[id, src , trg , status, payment amount, tx_er, tx_er_hash]
                for data in self.dchannel.channel.data:
                    if data[0] in BlitzProtocol.all_failedTxs:
                        lock_released = False
                        # if the same tx which has gone through this channel has gone back and released the lock
                        for datatest in self.dchannel.channel.data:
                            if data[0] == datatest[0] and (datatest[3] == 'RELEASED' or datatest[3] == 'REVOKED'):
                                lock_released = True
                        if lock_released == False:
                            print("HERE")
                            BlitzProtocol.inflight_failure.pop(ind)
                            BlitzProtocol.collateral_failure.append(tx)
                            tx.inflight_failure_blitz = False
                            tx.collateral_failure_blitz = True
                            break
            else:
                BlitzProtocol.final_failure.append(tx)
            return False
        return True

    '''
        Locks the money in the channel w/ this contract if check() returns True
    '''

    def lock(self):
        assert self.dchannel is not None
        self.dchannel.balance -= self.payment_amount
        self.dchannel.locked_balance += self.payment_amount

        simulate_state_agreement(self.dchannel)

        self.status = LOCKED
        self.save_data()

    '''
        Checks whether the hash of the tx_er from the receiver contract is the same one as his
    '''

    def tx_er_check(self, contractWithReceiver):
        contractWithReceiver.tx.curr_contract_index -= 1
        self.tx.curr_contract_index_fromTheBack += 1
        # checking the hash
        if self.tx_er_hash == contractWithReceiver.tx_er_hash:
            return True
        else:
            return False

    '''
        Payment goes through either when time T expired or version of the protocol is FastBlitz
    '''

    # release after time T -- time T would have to be specified
    def release(self):
        assert self.dchannel is not None
        assert self.status == LOCKED

        # after time T this should be released

        simulate_state_agreement(self.dchannel)

        self.dchannel.locked_balance -= self.payment_amount
        brother_channel = self.dchannel.get_brother_channel()
        brother_channel.balance += self.payment_amount
        self.status = RELEASED
        self.save_data()
        return True

    '''
        Payment is revoked either in:
            honest case during forwarding and the revoking is done backwards
            tx_er has been tampered w/ (to be implemented in attack strategies)
            config value force_revoke_enabled=True
    '''

    # if tx er is posted and T< 3*delta +tc
    def revoke(self):
        assert self.dchannel is not None

        simulate_state_agreement(self.dchannel)

        self.dchannel.balance += self.payment_amount
        self.dchannel.locked_balance -= self.payment_amount
        self.status = REVOKED
        self.save_data()

    '''
        Saves the data seen by each node
    '''

    def save_data(self):
        tx_er = {
            "id": self.tx_er['id'],
            "epsilon": self.tx_er['epsilon'],  # some predefined small amount
            "published": self.tx_er['published'],
            "rList": self.tx_er['rList']
        }
        contract_record = [
            self.tx.id,
            self.dchannel.src.pk,
            self.dchannel.trg.pk,
            self.status,
            self.payment_amount,
            tx_er,
            self.tx_er_hash,
        ]

        # print(contract_record)
        self.dchannel.channel.data.append(tuple(contract_record))
