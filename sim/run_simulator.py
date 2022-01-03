import sys
from os import replace

import numpy as np

from blitz_protocol import BlitzProtocol, BlitzContract
from constants import FAILED
from data_preprocessing import process_network_data, retrieve_program_input
from htlc_protocol import HTLCProtocol, HTLCContract
from network_topology import NetworkTopology
from simulator import Simulator
from transactions import TransactionGenerator
from configparser import ConfigParser


if __name__ =="__main__":
    #instantiate parser for reading config file
    config=ConfigParser()

    #parse config.ini file
    config.read('config.ini')

    #read values
    blitzVersion=config.get('RunParams','version')
    force_revoke_enabled=config.getboolean('RunParams','force_revoke_enabled')
    percentage_of_failed=config.getfloat('RunParams','percentage_of_failed')
    epoch_size=config.getint('RunParams','epoch_size')

    #retrieve arguments "sample.json" & "params.json"
    network_data, params= retrieve_program_input(sys.argv)

    #preprocess the network data
    nodes_df, network_df = process_network_data(network_data)


    # build the network topology - prepare the channels (make directed edges-->prepare them-->make channels)
    networkBlitz = NetworkTopology(nodes_df, network_df,params["payment_amount"],params["capacity_assignment"]) #network for Blitz

    networkHtlc=NetworkTopology(nodes_df, network_df,params["payment_amount"],params["capacity_assignment"]) #network for HTLC

    #generate random transactions
    tx_generator = TransactionGenerator(networkBlitz,networkHtlc)
    transactions,transactions_htlc = tx_generator.generate(params["number_of_transactions"], params["payment_amount"],params["one_amount_for_all_txs"])




    # select the protocol htlc
    htlc_protocol=HTLCProtocol(networkHtlc,HTLCContract)

    simulatorHtlc=Simulator(htlc_protocol)
    simulatorHtlc.epoch_size = epoch_size
    simulatorHtlc.percentage_of_failed = percentage_of_failed
    simulatorHtlc.simulate_transactions(transactions_htlc)

    # select the protocol Blitz
    # protocol = Protocol(network, Contract)
    protocol = BlitzProtocol(networkBlitz, BlitzContract, blitzVersion, force_revoke_enabled)

    # perform simulation
    simulator = Simulator(protocol)
    simulator.epoch_size = epoch_size
    simulator.percentage_of_failed = percentage_of_failed
    simulator.simulate_transactions(transactions)

    #print what have nodes along the path learned aboout a tx in Blitz
    failedBlitz=[]
    failed_bcs_to_locked_balance_blitz = []
    failed_bcs_of_locked_balance_on_Failedtxs_blitz = []

    for t in transactions:
        print("Blitz \n"+ str(t.status)+ "  failed purposely:  " + str(t.failed_purposely))
        if t.status ==FAILED and t.failed_bcs_of_locked_balance_blitz==True:
            print("Failed because of locked balance")
            failed_bcs_to_locked_balance_blitz.append(t)
        elif t.status ==FAILED and t.failed_bcs_of_locked_balance_on_Failedtxs_blitz==True:
            print("Failed because of locked balance on Failed txs")
            failed_bcs_of_locked_balance_on_Failedtxs_blitz.append(t)
        elif t.status==FAILED:  failedBlitz.append(t)
        for dchannel in t.dchannels_path:
            for data in dchannel.channel.data:
                if data[0]==t.id:
                    print(data)

    failedHTLC = []
    failed_bcs_to_locked_balance_htlc = []
    failed_bcs_of_locked_balance_on_Failedtxs_htlc = []


    for t in transactions_htlc:
        print("HTLC \n" + str(t.status)+ "  failed purposely:  "+ str(t.failed_purposely))
        if t.status ==FAILED and t.failed_bcs_of_locked_balance_htlc==True:
            print("Failed because of locked balance")
            failed_bcs_to_locked_balance_htlc.append(t)
        elif t.status ==FAILED and t.failed_bcs_of_locked_balance_on_Failedtxs_htlc==True:
            print("Failed because of locked balance on Failed txs")
            failed_bcs_of_locked_balance_on_Failedtxs_htlc.append(t)
        elif t.status==FAILED:
                failedHTLC.append(t)
        for dchannel in t.dchannels_path:
            for data_htlc in dchannel.channel.data_htlc:
                if data_htlc[0]==t.id:
                    print(data_htlc)
        print("\n\n")

    print("Successfully reached receiver in Blitz: " + str(BlitzProtocol.successfully_reached_receiver_counter))

    print("Failed Blitz Txs:" +str(len(failedBlitz)))

    print("Failed Blitz due to locked balance TXs:" + str(len(failed_bcs_to_locked_balance_blitz)))
    print(len(BlitzProtocol.locked_balance_failure))

    print("Failed Blitz due to locked balance on failed_txs:" + str(len(failed_bcs_of_locked_balance_on_Failedtxs_blitz)))
    print(len(BlitzProtocol.locked_balance_onFailedtxs_failure))

    print("Successfully reached receiver in HTLC: " + str(HTLCProtocol.successfully_reached_receiver_counter))

    print("Failed HTLC TXs:" +str(len(failedHTLC)))

    print("Failed HTLC due to locked balance TXs:" + str(len(failed_bcs_to_locked_balance_htlc)))
    print(len(HTLCProtocol.locked_balance_failure))

    print("Failed HTLC due to locked balance on failed_txs:" + str(len(failed_bcs_of_locked_balance_on_Failedtxs_htlc)))
    print(len(HTLCProtocol.locked_balance_onFailedtxs_failure))

    file = open("myfile.txt", "a")  # append mode
    file.write("No_of_txs: " + str(params["number_of_transactions"])+"\n")
    file.write("Epoch size " +str(epoch_size)+ "\n")
    file.write("Percentage of failed: "+ str(percentage_of_failed)+ "\n")
    file.write("Successfully reached receiver in Blitz: " + str(BlitzProtocol.successfully_reached_receiver_counter)+ "\n")
    file.write("Failed Blitz Txs:" + str(len(failedBlitz))+ "\n")
    file.write("Failed Blitz due to locked balance TXs:" + str(len(failed_bcs_to_locked_balance_blitz))+ "\n")
    file.write("Failed Blitz due to locked balance on failed_txs:" + str(len(failed_bcs_of_locked_balance_on_Failedtxs_blitz))+ "\n")
    file.write("Successfully reached receiver in HTLC: " + str(HTLCProtocol.successfully_reached_receiver_counter)+ "\n")
    file.write("Failed HTLC TXs:" + str(len(failedHTLC))+ "\n")
    file.write("Failed HTLC due to locked balance TXs:" + str(len(failed_bcs_to_locked_balance_htlc))+ "\n")
    file.write("Failed HTLC due to locked balance on failed_txs:" + str(len(failed_bcs_of_locked_balance_on_Failedtxs_htlc))+ "\n\n")
    file.close()