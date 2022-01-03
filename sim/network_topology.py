import random

import networkx as nx
import numpy as np
import pandas as pd

from utils import calculate_tx_fee
from utils import calculate_routing_weight


class NetworkTopology:
    '''
    @nodes_df -- [pd.df] w/ attr: [pub_key last update]
    @channels_df -- [pd.df] w/ attr: [node1_pub node2_pub last_update capacity channel_id node1_policy node2_policy]
    @amount -- [int] upper bound on the tx amount or the exact amount of every tx
    @capacity_assignment -- [str] how the capacity should be distributed
    '''

    def __init__(self, nodes_df, channels_df, amount, capacity_assignment):
        # self.drop_low_cap = True
        self.nodes_map = self.create_nodes_map(nodes_df)
        directed_edges_df = self.make_directed_edges(channels_df)
        directed_channels_df = self.prepare_cahnnels(directed_edges_df, amount)
        self.channels_map = self.create_channels_map(directed_channels_df, capacity_assignment)
        self.digraph = None

    '''
        Creates a map like ( pub_key ) : [pub_key,last_update]
    Params:
        @nodes_df -- [pd.df] w/ attr. [pub_key last_update]
    Returns:
        @nodes_map -- [map] like ( pub_key ) : [pub_key,last_update]
    '''

    def create_nodes_map(self, nodes_df):
        # create a list of tuples with the node's data
        records = nodes_df.to_records(index=False)
        node_tuples = list(records)

        nodes_map = dict()
        for t in node_tuples:
            nodes_map[t[0]] = Node(t[0], t[1])

        return nodes_map

    '''
        Creates a map like ( node1.pk , node2.pk ) : Channel.object ( contains two directed edges from directed_channels_df )
    Params:
        @directed_channels_df -- [pd.df] w/ attr. [node1_pub,node2_pub,last_update,capacity,channel_id, fee_base,fee_rate. min_htlc,time_lock_delta,total_fee,risk_factor,routing_weight]
        @capacity_assignment -- [str] how capacity should be distibuted(Left, Right, Random)     
    Returns:
        @channels_map -- [map] like ( node1.pk , node2.pk ) : Channel.object
    '''

    def create_channels_map(self, directed_channels_df, capacity_aasignment):
        # get keys for the map of directed edges
        keys = list(zip(directed_channels_df["node1_pub"], directed_channels_df["node2_pub"]))

        # make a unique set of channels(between nodes can exist only one channel)
        channels = set()
        for s, t in keys:
            if (s, t) in channels or (t, s) in channels:
                continue
            else:
                channels.add((s, t))

        # make a map of directed edges like:
        # (src,trg):[node1_pub,node2_pub,last_update,capacity,channel_id, fee_base,fee_rate. min_htlc,time_lock_delta,total_fee,risk_factor,routing_weight]
        vals = [list(item) for item in zip(directed_channels_df["node1_pub"], directed_channels_df["node2_pub"],
                                           directed_channels_df["last_update"],
                                           directed_channels_df["capacity"], directed_channels_df["channel_id"],
                                           directed_channels_df["fee_base_msat"],
                                           directed_channels_df["fee_rate_milli_msat"],
                                           directed_channels_df["min_htlc"], directed_channels_df["time_lock_delta"],
                                           directed_channels_df["total_fee"], directed_channels_df["risk_factor"],
                                           directed_channels_df["routing_weight"])]
        map_of_directed = dict(zip(keys, vals))

        channels_map = {}

        # for each channel
        for s, t in channels:
            node1 = self.nodes_map[s]
            node2 = self.nodes_map[t]
            from_node1_to_node2 = map_of_directed[s, t]  # take first directed edge in the channel
            from_node2_to_node1 = map_of_directed[(t, s)]  # take the second directed edge in the channel
            channel = Channel(node1, node2, from_node1_to_node2, from_node2_to_node1)
            channel.calculate_balance(capacity_aasignment)
            channels_map[(node1.pk, node2.pk)] = channel

        # for each directed channel in dataframe
        # for index, row in directed_channels_df.iterrows():
        #     # retrieve the nodes
        #     node1 = self.nodes_map[row["node1_pub"]]
        #     node2 = self.nodes_map[row["node2_pub"]]
        #
        #
        #     channel = Channel(node1, node2, row)
        #     channel.calculate_balance(0)
        #     channels_map[(node1.pk, node2.pk)] = channel
        #
        return channels_map

    '''
        Function transforms channels into directed egdes of channels, filling missing policy values
    Params:
        @channels_df -- [pd.df] w/ attr: [node1_pub node2_pub last_update capacity channel_id node1_policy node2_policy]
    Returns:
        @directed_edges_df -- [pd.df] w/ attr: [node1_pub,node2_pub,last_update,capacity,channel_id,disabled,fee_base,fee_rate, min_htlc,time_lock_delta]
    '''

    def make_directed_edges(self, channels_df,
                            policy_keys=['disabled', 'fee_base_msat', 'fee_rate_milli_msat', 'min_htlc',
                                         'time_lock_delta']):
        directed_edges = []

        for idx, row in channels_df.iterrows():
            e1 = [row[x] for x in ["node1_pub", "node2_pub", "last_update", "capacity", "channel_id"]]
            e2 = [row[x] for x in ["node2_pub", "node1_pub", "last_update", "capacity", "channel_id"]]
            # i think this is redundant
            assert (row["node1_policy"] != None)
            e1 += [row["node1_policy"][x] for x in policy_keys]
            assert (row["node2_policy"] != None)
            e2 += [row["node2_policy"][x] for x in policy_keys]
            directed_edges += [e1, e2]
        cols = ["node1_pub", "node2_pub", "last_update", "capacity", "channel_id"] + policy_keys
        directed_edges_df = pd.DataFrame(directed_edges, columns=cols)

        # fill missing policy values with most frequent values
        directed_edges_df = directed_edges_df.fillna(
            {"disabled": False, "fee_base_msat": 1000, "fee_rate_milli_msat": 10, "min_htlc": 0,
             "time_lock_delta": 144})
        for col in ["fee_base_msat", "fee_rate_milli_msat", "min_htlc"]:
            directed_edges_df[col] = directed_edges_df[col].astype("float64")

        return directed_edges_df

    '''
        Fuction prepares edges in a way: drops edges with lower capacity than the max amount of transaction (if enabled, default=not enabled)
                                        aggregates all multi-edges between two nodes leaving only one edge in each direction
                                        calculates total_fee of each edge 
                                        calculates the risk_factor of each edge
                                        calculates the routing weight of each edge                             
    Params:
        @directed_edges_df -- [pd.df] w/ attr: [node1_pub,node2_pub,last_update,capacity,channel_id,disabled,fee_base,fee_rate, min_htlc,time_lock_delta]
        @amount -- [int] upper bound of the tx amount                        
    Returns:
        @directed_aggr_edges -- [pd.df] w/ attr:[node1_pub,node2_pub,last_update,capacity,channel_id,fee_base,fee_rate, min_htlc,time_lock_delta]
    '''

    def prepare_cahnnels(self, directed_edges_df, amount):
        tmp_edges_df = directed_edges_df.copy()
        # remove the edges with capacity below treshold -- not doing it for now
        # if self.drop_low_cap:
        #     tmp_edges_df=tmp_edges_df[tmp_edges_df["capacity"]>=amount]
        #

        # aggregate multi-edges
        grouped = tmp_edges_df.groupby(["node1_pub", "node2_pub"])
        directed_aggr_edges = grouped.agg({
            "last_update": "max",
            "capacity": "sum",
            "channel_id": "min",  # this can be potentially problematic but for the current situation is OK!
            "fee_base_msat": "mean",
            "fee_rate_milli_msat": "mean",
            "min_htlc": "min",
            "time_lock_delta": "mean",

        }).reset_index()

        # calculate the edge cost
        directed_aggr_edges["total_fee"] = calculate_tx_fee(directed_aggr_edges, amount)

        # generate random risk factor
        directed_aggr_edges["risk_factor"] = np.random.choice([1, 10, 100, 1000], size=directed_aggr_edges.shape[0],
                                                              replace=True) #im not using this so it can stay

        # calculate routing weight
        directed_aggr_edges["routing_weight"] = calculate_routing_weight(directed_aggr_edges, amount)

        return directed_aggr_edges

    '''
        Creates a digraph with nodes and dchannels with edge attr. 'weight' as total_fee
    '''

    def create_digraph(self):
        g = nx.DiGraph()

        for node in self.nodes_map.keys():
            g.add_node(node)

        for channel in self.channels_map.values():
            g.add_edges_from(channel.create_directed_edges())

        return g

    '''
        Gets the created digraph
    '''

    def get_graph(self):
        if self.digraph is not None:
            return self.digraph

        self.digraph = self.create_digraph()

        # do the analysis of strongly connected componenets-- biggest component contains more than 99% of the nodes , there are only 6 components
        array_of_stongly_connected_components = [
            len(c)
            for c in sorted(nx.strongly_connected_components(self.digraph), key=len, reverse=True)
        ]
        largest = max(nx.strongly_connected_components(self.digraph), key=len)
        # do computations only on largest component

        g = nx.DiGraph()

        for node in largest:
            g.add_node(node)

        for channel in self.channels_map.values():
            if channel.node1.pk in largest and channel.node2.pk in largest:
                g.add_edges_from(channel.create_directed_edges())

        self.digraph = g
        return self.digraph

    '''
        Function gets the directed channel which goes from node pk1 to pk2
    '''

    def get_directed_channel(self, pk1, pk2):
        if (pk1, pk2) in self.channels_map:
            return self.channels_map[(pk1, pk2)].directed_channels[pk1]
        elif (pk2, pk1) in self.channels_map:
            return self.channels_map[(pk2, pk1)].directed_channels[pk1]

        print("ERROR: Channel not found")
        return None


class Node:
    '''
    @pk -- [string?] public key of the node in the graph
    @last_update -- [int?] measures when was the node's last update
    '''

    def __init__(self, pk, last_update):
        self.pk = pk
        self.last_update = last_update
        self.channels = []

        self.fict_private_key = None
        self.fict_public_key = None

    '''
        Function adds a channel to the node channels array
    Params:
        @channel -- [Channel] the Channel.object that conects respective node with its neighbour
    '''

    def add_channel(self, channel):
        self.channels.append(channel)


class Channel:
    """
    @node1 -- [Node] @node2 -- [Node] @from_node1_to_node2 -- [array] w/ attr: [node1_pub,node2_pub,last_update,
    capacity,channel_id, fee_base,fee_rate,min_htlc, time_lock_delta, total_fee,risk_factor,routing_weight]
    @from_node2_to_node1 -- [array] w/ attr: [node1_pub,node2_pub,last_update,capacity,channel_id, fee_base,fee_rate,
    min_htlc, time_lock_delta, total_fee,risk_factor,routing_weight]
    """

    def __init__(self, node1, node2, from_node1_to_node2, from_node2_to_node1):
        self.node1 = node1
        self.node2 = node2

        # add assert for id also
        self.id = min(int(from_node1_to_node2[4]),
                      int(from_node2_to_node1[
                              4]))  # get min id for the channel -- turn this to hash because it might be potentially problematic
        assert (from_node1_to_node2[3] == from_node2_to_node1[
            3])  # assert for making sure both edges have the same capacity

        self.capacity = max(float(from_node1_to_node2[3]),
                            float(from_node2_to_node1[3]))  # get max capacity for the channel
        self.last_update = max(from_node1_to_node2[2], from_node2_to_node1[2])

        # the channel is divided in two directed channels
        self.directed_channels = {}  # maps src public key to its directed channel
        self.directed_channels[node1.pk] = DirectedChannel(node1, node2, from_node1_to_node2, self)
        self.directed_channels[node2.pk] = DirectedChannel(node2, node1, from_node2_to_node1, self)
        # holds the information of all the payment events that pass through this channel
        self.data = []
        self.data_htlc=[]

        self.id = hash(hash(self.node1) + hash(self.node2) + hash(self.capacity) + hash(self.last_update))

        # Add this channel to each node (probably will be useful later)
        self.node1.add_channel(self)
        self.node2.add_channel(self)

    '''
        Function distributes balance between two nodes in the channel
    Params:
        @capacity_assignment -- [str] balance can be distributed as 50/50(default), Random, Left or Right
    '''

    def calculate_balance(self, capacity_assignment="default", balance_policy=0):
        node1_balance = self.capacity / 2.0
        node2_balance = self.capacity / 2.0
        if capacity_assignment == "Random":
            # Assing balances randomly
            node1_balance = random.randint(0, self.capacity)
            node2_balance = self.capacity - node1_balance
        elif capacity_assignment == "Left":
            node1_balance = self.capacity
            node2_balance = 0
        elif capacity_assignment == "Right":
            node1_balance = 0
            node2_balance = self.capacity
        self.directed_channels[self.node1.pk].balance = node1_balance
        self.directed_channels[self.node2.pk].balance = node2_balance

    '''
        Returns an array of edges w/ attr: [src.pk trg.pk weight:total_fee] --need this to create nx.Digraph later
    '''

    def create_directed_edges(self):
        edges = []
        for dchannel in self.directed_channels.values():
            edges.append((dchannel.src.pk, dchannel.trg.pk, {"weight": dchannel.get_total_fee()}))

        return edges


class DirectedChannel:
    """
    @src -- [Node] the source node
    @trg -- [Node] the target node
    @policy -- [array] w/ attr: [node1_pub,node2_pub,last_update,capacity,channel_id, fee_base,fee_rate,min_htlc,time_lock_delta,total_fee,risk_factor,routing_weight]
    @channel -- [Channel] channel containing this directed channel
    """

    def __init__(self, src, trg, policy, channel):
        self.channel = channel
        self.src = src
        self.trg = trg

        # policy attributes
        # self.disabled = policy["disabled"]
        self.fee_base_msat = int(policy[5])  # "fee_base_msat"
        self.fee_rate_milli_msat = int(policy[6])
        self.min_htlc = int(policy[7])
        self.time_lock_delta = int(policy[8])
        # calculated attributes
        self.total_fee = policy[9]
        self.risk_factor = policy[10]
        self.routing_weight = policy[11]

        self.balance = 0
        self.locked_balance = 0

    '''
        Gets total_fee as a  weight for the creation of digraph
    '''
    def get_total_fee(self):
        return self.total_fee

    '''
        Gets dchannel in the other direction 
    '''
    def get_brother_channel(self):
        return self.channel.directed_channels[self.trg.pk]

    '''
        Calculates a fee this node for the given amount
    '''
    def calculate_fee(self, amount):
        return (self.fee_base_msat / 1000.0) + amount * self.fee_rate_milli_msat / 10.0 ** 6
