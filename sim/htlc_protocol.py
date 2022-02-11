from utils import create_hash, create_preimage, get_random_string, generate_keys_for_nodes, simulate_state_agreement, \
    generate_tx_er
from protocol import Protocol, Contract
from constants import FAILED, SUCCESS, SETUP_DONE, REVOKING, RELEASING, FORWARDING, NOT_STARTED, LOCKED, RELEASED, \
    REVOKED, TX_ER_CHECKING, TX_ER_PUBLISHED, INSTANT_REVOKING, GO_IDLE, FORCING_REVOKE, RELEASE_ALL, \
    FINISHED_FORWARDING

TIMELOCK = 10000
TIMELOCK_DELTA = 100


class HTLCProtocol(Protocol):
    successfully_reached_receiver_txs = []
    successfully_reached_receiver_counter = 0

    all_failedTxs = []
    failed_purposely = []

    final_failure = []
    inflight_failure = []
    collateral_failure = []

    def setup(self, tx):
        generate_keys_for_nodes(tx)
        tx.preimage = create_preimage(tx)
        tx.preimage_hash = create_hash(tx.preimage)

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
                HTLCProtocol.successfully_reached_receiver_txs.append(tx)
                HTLCProtocol.successfully_reached_receiver_counter += 1
                tx.status = GO_IDLE
            else:
                prev_contract = tx.pending_contracts[0]
                new_contract = self.create_next_contract(prev_contract, dchannel)
                if not self.forward_contract(tx, new_contract):
                    tx.status = REVOKING

        elif status == GO_IDLE:
            if tx.premarked_as_failed == True:
                tx.set_delays_htlc(round_counter,epoch_size)
                tx.status = REVOKING
                HTLCProtocol.all_failedTxs.append(tx.id)
            else:
                tx.status = RELEASE_ALL
            return


        elif status == RELEASE_ALL:
            if tx.release_all():
                # print("Everybody released.")
                tx.status = SUCCESS
            else:
                print("RELEASE_ALL ERROR")

        elif status == RELEASING:
            contract = tx.get_last_pending_contract()
            if contract is not None:
                if not contract.release():
                    print("RELEASE ERROR")
            else:
                tx.status = SUCCESS

        elif status == REVOKING:
            if tx.curr_contract_index < len(tx.delays_htlc):
                if tx.delays_htlc[tx.curr_contract_index] > round_counter:
                    return
            contract = tx.get_last_pending_contract()
            if contract is not None:
                contract.revoke()
            else:
                tx.status = FAILED


class HTLCContract(Contract):
    def __init__(self, tx, dchannel):
        self.tx = tx
        self.dchannel = dchannel
        self.payment_amount = None
        self.status = None
        self.timelock = TIMELOCK
        self.preimage = None
        self.preimage_hash = None

    @classmethod
    def new_contract(cls, tx, next_dchannel):
        contract = cls(tx, next_dchannel)
        contract.payment_amount = tx.payment_amount + tx.total_amount_fees
        contract.preimage_hash = tx.preimage_hash
        return contract

    @classmethod
    def get_next_contract(cls, prev_contract, next_dchannel):
        contract = cls(prev_contract.tx, next_dchannel)
        contract.payment_amount = prev_contract.payment_amount - next_dchannel.calculate_fee(
            prev_contract.payment_amount)
        contract.timelock = prev_contract.timelock - TIMELOCK_DELTA
        contract.preimage_hash = prev_contract.preimage_hash
        return contract

    def check(self, tx):
        if (
                self.dchannel.balance < self.payment_amount or  # the balance is not enough
                self.dchannel.min_htlc > self.payment_amount  # the payment amount is below the minimum
                # self.timelock < 0   # the timelock is not enough -- i dont think the timelock should be considered in this case
        ):
            # this checks if the failure happend due to the purposely failed transactions which locked coins
            if (
                    self.dchannel.locked_balance + self.dchannel.balance >= self.payment_amount > self.dchannel.min_htlc
                    # self.timelock >0
            ):
                ind = len(HTLCProtocol.inflight_failure)
                HTLCProtocol.inflight_failure.append(tx)
                #tx.inflight_failure_htlc = True

                # data is an array:[id, src , trg , status, payment amount, tx_er, tx_er_hash]
                for data_htlc in self.dchannel.channel.data_htlc:
                    if data_htlc[0] in HTLCProtocol.all_failedTxs:
                        lock_released = False
                        # if the same tx which has gone through this channel has gone back and released the lock
                        for datatest in self.dchannel.channel.data_htlc:
                            if data_htlc[0] == datatest[0] and (datatest[3] == 'RELEASED' or datatest[3] == 'REVOKED'):
                                lock_released = True
                        if lock_released == False:
                            print("HERE")
                            HTLCProtocol.inflight_failure.pop(ind)
                            HTLCProtocol.collateral_failure.append(tx)
                            #tx.inflight_failure_htlc = False
                            #tx.collateral_failure_htlc = True
                            break
            else:
                HTLCProtocol.final_failure.append(tx)
            return False
        return True

    def lock(self):
        assert self.dchannel is not None
        self.dchannel.balance -= self.payment_amount  # nothing about the fee here
        self.dchannel.locked_balance += self.payment_amount

        simulate_state_agreement(self.dchannel)

        self.status = LOCKED
        self.save_data()

    def release(self):
        assert self.dchannel is not None
        assert self.status == LOCKED

        preimage = self.tx.preimage

        if create_hash(preimage) != self.preimage_hash:
            return False

        simulate_state_agreement(self.dchannel)

        self.preimage = preimage
        self.dchannel.locked_balance -= self.payment_amount
        brother_channel = self.dchannel.get_brother_channel()
        brother_channel.balance += self.payment_amount
        self.status = RELEASED
        self.save_data()
        return True

    def revoke(self):
        assert self.dchannel is not None

        simulate_state_agreement(self.dchannel)

        self.dchannel.balance += self.payment_amount
        self.dchannel.locked_balance -= self.payment_amount
        self.status = REVOKED
        self.save_data()

    def save_data(self):
        contract_record = [
            self.tx.id,
            self.dchannel.src.pk,
            self.dchannel.trg.pk,
            self.status,
            self.payment_amount,
            self.preimage_hash,
            self.preimage
        ]

        # print(contract_record)
        self.dchannel.channel.data_htlc.append(tuple(contract_record))
