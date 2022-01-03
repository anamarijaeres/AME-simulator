import sys

from utils import load_json_file
import pandas as pd

NODE_KEYS = ["pub_key", "last_update"]
CHANNEL_KEYS = ["node1_pub", "node2_pub", "last_update", "capacity", "channel_id", 'node1_policy', 'node2_policy']


'''
        Function takes two imputs sample and params and processes them.
    Params:
        @args -- [string] names of the files containing the json file of the ln_snapshot and parameters
    Returns:
        @network_data -- [json_file]  
        @parameters -- [json_file]
'''
def retrieve_program_input(args):
    if(len(sys.argv)!=3):
        print(" You must provide 2 parameters! ")
        print(" run_simulator.py <json_file> <parameter file>")
        sys.exit()

    network_data=load_json_file(sys.argv[1])
    parameters = load_json_file(sys.argv[2])

    parameters["payment_amount"] = int(parameters["payment_amount"])
    parameters["number_of_transactions"] = int(parameters["number_of_transactions"])
    parameters["capacity_assignment"]=str(parameters["capacity_assignment"])
    parameters["max_htlc"]=int(parameters["max_htlc"])
    parameters["protocol"]=str(parameters["protocol"])
    parameters["one_amount_for_all_txs"]=bool(parameters["one_amount_for_all_txs"])

    return network_data, parameters

'''
        Function makes two dataframes: first containing edges and second containing nodes.
    Params:
        @network -- [json_file] 
    Returns:
        @nodes_df -- [pd.df] w/ attr: [pub_key last update]
        @channels_df -- [pd.df] w/ attr: [node1_pub node2_pub last_update capacity channel_id node1_policy node2_policy]
'''
def process_network_data(network):
    channels_df = pd.DataFrame(network["edges"])[CHANNEL_KEYS]

    channels_df["capacity"] = channels_df["capacity"].astype("int64")
    channels_df["last_update"] = channels_df["last_update"].astype("int64")

    # eliminate channels with loops
    channels_df = channels_df[channels_df["node1_pub"] != channels_df["node2_pub"]]

    # check the policies
    channels_df = channels_df[
        (~channels_df["node1_policy"].isnull()) &
        (~channels_df["node2_policy"].isnull())
        ]

    nodes_df = pd.DataFrame(network["nodes"])[NODE_KEYS]
    return nodes_df, channels_df

