# AME simulator

A simulator developed for my master thesis.
The implemented simulator simulates the processing of transactions in a payment channel network given a specific protocol.




## Getting Started

### Prerequisites

Requirements for the software and other tools to build, test and push 
- [Python](https://www.python.org/downloads/)



### Installing

To instal python:
    
    python install 


## Input parameters

In the file data/params.json:

-  payment_amount--payment amount of the transaction/transactions--**Float**: *[0,inf]*
-  number_of_transactions--the total number of transactions the simulator has to simulate--**Integer**: *[0,inf]*

-  capacity_assignment--option to assign capacity to the left or the right user in the channel--**String**: *Left|Right|Random|Default*
- one_amount_for_all_txs--flag marking if all generated transactions have the same value--**Boolean**: *True|False*

In the file sim/config.ini:

- version--the version of the protocol--**String**: *SimpleBlitz--the version where the sender upon receiving the confirmation goes idle and after time T the transaction gets processed|FastBlitz--the version where the sender upon receiving the confirmation start transferring coins in the agreement with the right neighbour*
- percentage_of_failed-- percentage of generated transactions that will be initially marked as failed--**Float**: *[0,1]*
- delay_param--the time it takes to publish 1 block on chain, it correlates with operation_time parameter. The default time to publish 1 block is 10 minutes that is 600s.--**Float**: *[0, inf]*
- operation_time-- the time it takes to process 1 operation (for example setting up the HTLC contract between two users), default value is 10 ms =0.01s--**Float**: *[0, inf]*
