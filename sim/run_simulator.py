import copy
import random
import sys
from os import replace

import numpy as np

from blitz_protocol import BlitzProtocol, BlitzContract
from constants import FAILED
from data_preprocessing import process_network_data, retrieve_program_input
from htlc_protocol import HTLCProtocol, HTLCContract
from network_topology import NetworkTopology
from simulator import Simulator
from transactions import TransactionGenerator, Transaction
from configparser import ConfigParser
from constants import SUCCESS

if __name__ == "__main__":


    # instantiate parser for reading config file
    config = ConfigParser()

    # parse config.ini file
    config.read('config.ini')

    # read values
    blitzVersion = config.get('RunParams', 'version')
    force_revoke_enabled = config.getboolean('RunParams', 'force_revoke_enabled')
    percentage_of_failed = config.getfloat('RunParams', 'percentage_of_failed')
    delay_param = config.getint('RunParams', 'delay_param')
    operation_time = config.getfloat('RunParams', 'operation_time')

    # time to publish 1 block is 10 minutes == 600s
    block = 600
    delay_in_operations = block / operation_time

    # retrieve arguments "sample.json" & "params.json"
    network_data, params = retrieve_program_input(sys.argv)

    # preprocess the network data
    nodes_df, network_df = process_network_data(network_data)

    networkBlitz = NetworkTopology(nodes_df, network_df, params["payment_amount"],
                                   params["capacity_assignment"])  # network for Blitz
    core_nodes, core_channels = networkBlitz.find_skeleton()
    tx_amount_micropayments = networkBlitz.calculate_micropayment_amount(core_nodes, core_channels)
    tx_amount_concrete = networkBlitz.calculate_concrete_amount()

    amounts = [tx_amount_micropayments, tx_amount_concrete]

    percentages = [0.1, 0.2, 0.3]

    for percentage in percentages:

        for amount in amounts:
            Transaction.tx_counter = 0
            # build the network topology - prepare the channels (make directed edges-->prepare them-->make channels)
            networkBlitz = NetworkTopology(nodes_df, network_df, amount,
                                           params["capacity_assignment"])  # network for Blitz

            networkHtlc = NetworkTopology(nodes_df, network_df, amount,
                                          params["capacity_assignment"])  # network for HTLC



            # generate random transactions
            tx_generator = TransactionGenerator(networkBlitz, networkHtlc)
            transactions, transactions_htlc = tx_generator.generate(params["number_of_transactions"],
                                                                    amount,
                                                                    params["one_amount_for_all_txs"])
            # premark failed txs
            transactions, transactions_htlc = tx_generator.mark_failed_txs(transactions, transactions_htlc,
                                                                           percentage)

            # select the protocol Blitz
            protocol = BlitzProtocol(networkBlitz, BlitzContract, blitzVersion, force_revoke_enabled)

            # perform simulation
            simulator = Simulator(protocol, delay_in_operations)
            simulator.simulate_transactions(transactions)

            print("htlc")

            # select the protocol htlc
            htlc_protocol = HTLCProtocol(networkHtlc, HTLCContract)

            simulator.protocol = htlc_protocol
            simulator.epoch_size = delay_in_operations
            simulator.simulate_transactions(transactions_htlc)

            final_in_final = []
            final_in_inflight = []
            final_in_collateral = []
            final_in_success = []

            inflight_in_inflight = []
            inflight_in_final = []
            inflight_in_collateral = []
            inflight_in_success = []

            success_in_final = []
            success_in_inflight = []
            success_in_collateral = []

            succesfull_txs_blitz = 0
            succesfull_txs_htlc = 0

            for ind, tx in enumerate(transactions):
                if tx.final_failure_blitz and transactions_htlc[ind].final_failure_htlc:
                    final_in_final.append(transactions_htlc[ind])
                elif tx.final_failure_blitz and transactions_htlc[ind].inflight_failure_htlc:
                    final_in_inflight.append(transactions_htlc[ind])
                elif tx.final_failure_blitz and transactions_htlc[ind].collateral_failure_htlc:
                    final_in_collateral.append(transactions_htlc[ind])
                elif tx.inflight_failure_blitz and transactions_htlc[ind].final_failure_htlc:
                    inflight_in_final.append(transactions_htlc[ind])
                elif tx.inflight_failure_blitz and transactions_htlc[ind].inflight_failure_htlc:
                    inflight_in_inflight.append(transactions_htlc[ind])
                elif tx.inflight_failure_blitz and transactions_htlc[ind].collateral_failure_htlc:
                    inflight_in_collateral.append(transactions_htlc[ind])
                elif tx.final_failure_blitz and transactions_htlc[ind].status == SUCCESS:
                    final_in_success.append(transactions_htlc[ind])
                elif tx.inflight_failure_blitz and transactions_htlc[ind].status == SUCCESS:
                    inflight_in_success.append(transactions_htlc[ind])
                elif tx.status == SUCCESS and transactions_htlc[ind].final_failure_htlc:
                    success_in_final.append(transactions_htlc[ind])
                elif tx.status == SUCCESS and transactions_htlc[ind].inflight_failure_htlc:
                    success_in_inflight.append(transactions_htlc[ind])
                elif tx.status == SUCCESS and transactions_htlc[ind].collateral_failure_htlc:
                    success_in_collateral.append(transactions_htlc[ind])
                if tx.status == SUCCESS:
                    succesfull_txs_blitz += 1
                if transactions_htlc[ind].status == SUCCESS:
                    succesfull_txs_htlc += 1

            print("Successfully reached receiver in Blitz: " + str(BlitzProtocol.successfully_reached_receiver_counter))

            # print("Failure done on purpose blitz txs:" + str(len(BlitzProtocol.failed_purposely)))

            print("Final failure blitz txs:" + str(len(BlitzProtocol.final_failure)))

            print("Inflight failure blitz txs:" + str(len(BlitzProtocol.inflight_failure)))

            print("Collateral failure blitz txs:" + str(len(BlitzProtocol.collateral_failure)))

            print("Successfully reached receiver in HTLC: " + str(HTLCProtocol.successfully_reached_receiver_counter))

            # print("Failure done on purpose HTLC txs:" + str(len(HTLCProtocol.failed_purposely)))

            print("Final failure HTLC txs:" + str(len(HTLCProtocol.final_failure)))

            print("Inflight failure HTLC txs:" + str(len(HTLCProtocol.inflight_failure)))

            print("Collateral failure HTLC txs:" + str(len(HTLCProtocol.collateral_failure)))

            file = open("new.txt", "a")  # append mode
            file.write("No_of_accomplishable_txs: " + str(len(simulator.txs)) + "\n")
            file.write("Delay: " + str(delay_in_operations) + "\n")
            file.write("Percentage of failed: " + str(percentage) + "\n")
            file.write(
                "Successfully reached receiver in Blitz: " + str(
                    BlitzProtocol.successfully_reached_receiver_counter) + "\n")
            file.write("Successfull txs:" + str(succesfull_txs_blitz) + "\n")
            file.write("Final failure blitz txs:" + str(len(BlitzProtocol.final_failure)) + "\n")
            file.write("Inflight failure blitz txs:" + str(len(BlitzProtocol.inflight_failure)) + "\n")
            file.write("Collateral failure blitz txs:" + str(len(BlitzProtocol.collateral_failure)) + "\n")
            file.write(
                "Successfully reached receiver in HTLC: " + str(
                    HTLCProtocol.successfully_reached_receiver_counter) + "\n")
            file.write("Successfull txs:" + str(succesfull_txs_htlc) + "\n")
            file.write("Final failure HTLC txs:" + str(len(HTLCProtocol.final_failure)) + "\n")
            file.write("Inflight failure HTLC txs:" + str(len(HTLCProtocol.inflight_failure)) + "\n")
            file.write("Collateral failure HTLC txs:" + str(len(HTLCProtocol.collateral_failure)) + "\n\n")

            file.write("No of final to final:" + str(len(final_in_final)) + "\n")
            file.write("No of final to inflight:" + str(len(final_in_inflight)) + "\n")
            file.write("No of final to collateral:" + str(len(final_in_collateral)) + "\n")
            file.write("No of final to success:" + str(len(final_in_success)) + "\n\n")

            file.write("No of inflight to final:" + str(len(inflight_in_final)) + "\n")
            file.write("No of inflight to inflight:" + str(len(inflight_in_inflight)) + "\n")
            file.write("No of inflight to collateral:" + str(len(inflight_in_collateral)) + "\n")
            file.write("No of inflight to success:" + str(len(inflight_in_success)) + "\n \n")

            file.write("No of success to final:" + str(len(success_in_final)) + "\n")
            file.write("No of success to inflight:" + str(len(success_in_inflight)) + "\n")
            file.write("No of success to collateral:" + str(len(success_in_collateral)) + "\n \n\n")

            BlitzProtocol.successfully_reached_receiver_counter = 0
            BlitzProtocol.failed_purposely = []
            BlitzProtocol.final_failure = []
            BlitzProtocol.inflight_failure = []
            BlitzProtocol.collateral_failure = []

            HTLCProtocol.successfully_reached_receiver_counter = 0
            HTLCProtocol.failed_purposely = []
            HTLCProtocol.final_failure = []
            HTLCProtocol.inflight_failure = []
            HTLCProtocol.collateral_failure = []

            file.close()
