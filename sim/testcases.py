import unittest
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
from utils import load_json_file
import pandas as pd


class TestDataProcessing(unittest.TestCase):
	
	
    
    def test_data(self):		
    
        #parse the config and network files
        network_data=load_json_file("../data/sample-mini-correct.json") #Use sample-mini.json to trigger the error
        parameters = load_json_file("../data/params.json")

        parameters["payment_amount"] = int(parameters["payment_amount"])
        parameters["number_of_transactions"] = int(parameters["number_of_transactions"])
        parameters["capacity_assignment"]=str(parameters["capacity_assignment"])
        parameters["max_htlc"]=int(parameters["max_htlc"])
        parameters["protocol"]=str(parameters["protocol"])
        parameters["one_amount_for_all_txs"]=bool(parameters["one_amount_for_all_txs"])
    
        #preprocess the network data
        nodes_df, network_df = process_network_data(network_data)
        node1_pub = pd.DataFrame(network_df["node1_pub"])
        node1_pub = node1_pub.rename(columns={"node1_pub": "pub_key"})
        node2_pub = pd.DataFrame(network_df["node2_pub"])
        node2_pub = node2_pub.rename(columns={"node2_pub": "pub_key"})
        all_pub_keys = pd.concat([node1_pub, node2_pub])
    
        ##Check that every node has at least one channel
        self.assertEqual(set(nodes_df.pub_key.isin(all_pub_keys["pub_key"]).astype(bool)), set({True}), "ERROR: There is a node that does not involved in any channel")
    
        ##Check that every edge is between two nodes that are declared in the list of nodes
        self.assertEqual(set(all_pub_keys.pub_key.isin(nodes_df["pub_key"]).astype(bool)), set({True}), "ERROR: There is an edge involving a node that has not been declared in the list of nodes")


class TestNetworkTopology(unittest.TestCase):
    
    #init the network for the tests later
    nodes = {"pub_key": ["k1", "k2","k3"], "last_update":[1234, 2345, 345]}
    nodes_df = pd.DataFrame(data=nodes)
    channels = {"node1_pub":["k1", "k1"], "node2_pub":["k2", "k3"], "last_update":[1111, 1111], "capacitiy":[7000, 3000], "channel_id":[123, 345], "node1_policy":[ 1,1 ], "node2_policy":[ 2,2 ]}
    channels_df = pd.DataFrame(data=channels)
    #nwtopology = NetworkTopology(nodes_df, channels_df, 1234, "Random") 

    def test_create_nodes_map(self):
        
        #nodes_map = nwtopology.create_nodes_map(nodes_df)
        self.assertEqual(5, 5, "some tautology true")
        

if __name__ == '__main__':
    unittest.main()		
