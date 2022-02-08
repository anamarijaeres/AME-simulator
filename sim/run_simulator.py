import random
import sys
from os import replace
import unittest
import numpy as np
import pandas as pd

from blitz_protocol import BlitzProtocol, BlitzContract
from constants import FAILED
from data_preprocessing import process_network_data, retrieve_program_input
from htlc_protocol import HTLCProtocol, HTLCContract
from network_topology import NetworkTopology
from simulator import Simulator
from transactions import TransactionGenerator
from configparser import ConfigParser

EXECUTE_TESTS = 0	#Flag to activate/deactive the test cases TODO: Add this to config properly

def all_tests( ):
	test_data( )

	
def test_data( nodes_df, network_df ):
    print( "========================")
    print( "Starting test: test_data")
    
    ##Check that every node has at least one channel
    node1_pub = pd.DataFrame(network_df["node1_pub"])
    node1_pub = node1_pub.rename(columns={"node1_pub": "pub_key"})
    node2_pub = pd.DataFrame(network_df["node2_pub"])
    node2_pub = node2_pub.rename(columns={"node2_pub": "pub_key"})
    all_pub_keys = pd.concat([node1_pub, node2_pub])
    assert set(nodes_df.pub_key.isin(all_pub_keys["pub_key"]).astype(bool)) == set({True}), "ERROR: There is a node that does not involved in any channel"
   

    print( "test: test_data OK") 
    print( "========================")

if __name__ =="__main__":

    #random.seed(1)
    #state=random.getstate()
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
    if EXECUTE_TESTS:
        test_data( nodes_df, network_df )


    # build the network topology - prepare the channels (make directed edges-->prepare them-->make channels)
    networkBlitz = NetworkTopology(nodes_df, network_df,params["payment_amount"],params["capacity_assignment"]) #network for Blitz

    networkHtlc=NetworkTopology(nodes_df, network_df,params["payment_amount"],params["capacity_assignment"]) #network for HTLC

    #generate random transactions
    tx_generator = TransactionGenerator(networkBlitz,networkHtlc)
    transactions,transactions_htlc = tx_generator.generate(params["number_of_transactions"], params["payment_amount"],params["one_amount_for_all_txs"])

    transactions,transactions_htlc= tx_generator.mark_failed_txs(transactions,transactions_htlc,percentage_of_failed)

    # select the protocol Blitz
    protocol = BlitzProtocol(networkBlitz, BlitzContract, blitzVersion, force_revoke_enabled)

    # perform simulation
    simulator = Simulator(protocol, epoch_size, percentage_of_failed)
    # simulator.epoch_size = epoch_size
    # simulator.percentage_of_failed = percentage_of_failed
    simulator.simulate_transactions(transactions)

    print("htlc")

    #random.setstate(state)
    # select the protocol htlc
    htlc_protocol=HTLCProtocol(networkHtlc,HTLCContract)

    #simulatorHtlc=Simulator(htlc_protocol,epoch_size,percentage_of_failed)
    simulator.protocol=htlc_protocol
    simulator.epoch_size=epoch_size
    simulator.percentage_of_failed=percentage_of_failed
    simulator.simulate_transactions(transactions_htlc)
    # simulatorHtlc.epoch_size = epoch_size
    # simulatorHtlc.percentage_of_failed = percentage_of_failed
    #simulatorHtlc.simulate_transactions(transactions_htlc)



    #print what have nodes along the path learned aboout a tx in Blitz
    # failedBlitz=[]
    # inflight_failure = []
    # collateral_failure = []
    #
    # for t in transactions:

        # print("Blitz \n"+ str(t.status)+ "  failed purposely:  " + str(t.failed_purposely))
        # if t.status == FAILED  and t.inflight_failure_blitz==True:
        #     print("Failed because of locked balance")
        #     inflight_failure.append(t)
        # elif t.status ==FAILED and t.collateral_failure_blitz==True:
        #     print("Failed because of locked balance on Failed txs")
        #     collateral_failure.append(t)
        # elif t.status==FAILED:  failedBlitz.append(t)
    #     for dchannel in t.dchannels_path:
    #         for data in dchannel.channel.data:
    #             if data[0]==t.id:
    #                 print(data)
    #
    # failedHTLC = []
    # failed_bcs_to_locked_balance_htlc = []
    # failed_bcs_of_locked_balance_on_Failedtxs_htlc = []
    #
    #
    # for t in transactions_htlc:
    #     print("HTLC \n" + str(t.status)+ "  failed purposely:  "+ str(t.failed_purposely))
    #     if t.status ==FAILED and t.inflight_failure_htlc==True:
    #         print("Failed because of locked balance")
    #         failed_bcs_to_locked_balance_htlc.append(t)
    #     elif t.status ==FAILED and t.collateral_failure_htlc==True:
    #         print("Failed because of locked balance on Failed txs")
    #         failed_bcs_of_locked_balance_on_Failedtxs_htlc.append(t)
    #     elif t.status==FAILED:
    #             failedHTLC.append(t)
    #     for dchannel in t.dchannels_path:
    #         for data_htlc in dchannel.channel.data_htlc:
    #             if data_htlc[0]==t.id:
    #                 print(data_htlc)
    #     print("\n\n")

    print("Successfully reached receiver in Blitz: " + str(BlitzProtocol.successfully_reached_receiver_counter))

    print("Failure done on purpose blitz txs:" + str(len(BlitzProtocol.failed_purposely)))

    print("Final failure blitz txs:" + str(len(BlitzProtocol.final_failure)))

    print("Inflight failure blitz txs:" + str(len(BlitzProtocol.inflight_failure)))

    print("Collateral failure blitz txs:" + str(len(BlitzProtocol.collateral_failure)))


    print("Successfully reached receiver in HTLC: " + str(HTLCProtocol.successfully_reached_receiver_counter))

    print("Failure done on purpose HTLC txs:" + str(len(HTLCProtocol.failed_purposely)))

    print("Final failure HTLC txs:" + str(len(HTLCProtocol.final_failure)))

    print("Inflight failure HTLC txs:" + str(len(HTLCProtocol.inflight_failure)))

    print("Collateral failure HTLC txs:" + str(len(HTLCProtocol.collateral_failure)))

    file = open("myfile.txt", "a")  # append mode
    file.write("No_of_accomplishable_txs: " + str(len(simulator.txs))+"\n")
    file.write("Epoch size " +str(epoch_size)+ "\n")
    file.write("Percentage of failed: "+ str(percentage_of_failed)+ "\n")
    file.write("Successfully reached receiver in Blitz: " + str(BlitzProtocol.successfully_reached_receiver_counter)+ "\n")
    file.write("Failure done on purpose blitz txs:" + str(len(BlitzProtocol.failed_purposely)) + "\n")
    file.write("Final failure blitz txs:" + str(len(BlitzProtocol.final_failure))+ "\n")
    file.write("Inflight failure blitz txs:" + str(len(BlitzProtocol.inflight_failure)) + "\n")
    file.write("Collateral failure blitz txs:" + str(len(BlitzProtocol.collateral_failure)) + "\n")
    file.write("Successfully reached receiver in HTLC: " + str(HTLCProtocol.successfully_reached_receiver_counter)+ "\n")
    file.write("Failure done on purpose HTLC txs:" + str(len(HTLCProtocol.failed_purposely)) + "\n")
    file.write("Final failure HTLC txs:" + str(len(HTLCProtocol.final_failure))+ "\n")
    file.write("Inflight failure HTLC txs:" + str(len(HTLCProtocol.inflight_failure))+ "\n")
    file.write("Collateral failure HTLC txs:" + str(len(HTLCProtocol.collateral_failure))+ "\n\n")
    file.close()
    
    
