from Evaluation.cardinality_estimation import parse_query_single_table
from Evaluation.parse_query_imdb import prepare_join_queries
from Models.BN_ensemble_model import BN_ensemble
from time import perf_counter
import numpy as np
import pickle
import time
from multiprocessing import Pool, cpu_count
from functools import partial

def evaluate_cardinality_single_table(model_path, query_path, infer_algo, sample_size=1000):
    # load BN
    with open(model_path, 'rb') as f:
        BN = pickle.load(f)
    if BN.infer_machine is None:
        BN.infer_algo = infer_algo
        BN.init_inference_method()
    # read all queries
    with open(query_path) as f:
        queries = f.readlines()
    latencies = []
    q_errors = []
    for query_no, query_str in enumerate(queries):
        cardinality_true = int(query_str.split("||")[-1])
        query_str = query_str.split("||")[0]
        try:
            print(f"Predicting cardinality for query {query_no}: {query_str}")
            query = parse_query_single_table(query_str.strip(), BN)
            card_start_t = perf_counter()
            cardinality_predict = BN.query(query, sample_size=sample_size)
        except:
            #In the case, that the query itself is invalid or contains some values that are not recognizable by BN
            continue
        card_end_t = perf_counter()
        latency_ms = (card_end_t - card_start_t) * 1000
        if cardinality_predict == 0 and cardinality_true == 0:
            q_error = 1.0
        elif np.isnan(cardinality_predict) or cardinality_predict == 0:
            cardinality_predict = 1
            q_error = max(cardinality_predict / cardinality_true, cardinality_true / cardinality_predict)
        elif cardinality_true == 0:
            cardinality_true = 1
            q_error = max(cardinality_predict / cardinality_true, cardinality_true / cardinality_predict)
        else:
            q_error = max(cardinality_predict / cardinality_true, cardinality_true / cardinality_predict)
        print(f"latency: {latency_ms} and error: {q_error}")
        latencies.append(latency_ms)
        q_errors.append(q_error)

    #print("=====================================================================================")
    for i in [50, 90, 95, 99, 100]:
        print(f"q-error {i}% percentile is {np.percentile(q_errors, i)}")
    print(f"average latency is {np.mean(latencies)} ms")

    return latencies, q_errors

def evaluate_cardinality_stats(schema, model_path, query_path, infer_algo, learning_algo, max_parents):
    ensemble_location = "Benchmark/STATS/ensemble_loader.pkl"
    pairwise_rdc_path = "Benchmark/STATS/pairwise_rdc.pkl"
    
    parsed_queries, true = prepare_join_queries(ensemble_location, pairwise_rdc_path, query_path,
                                                join_3_rdc_based=False, true_card_exist=True)

    with open(query_path, "rb") as f:
        real_query = f.readlines()
    bn_ensemble = BN_ensemble(schema)
    for i in range(5):
        with open(f"{model_path}/{i}_{learning_algo}_{max_parents}.pkl", "rb") as f:
            bn = pickle.load(f)
            bn.infer_algo = infer_algo
            bn.init_inference_method()
        bn_ensemble.bns[i] = bn

    queries = bn_ensemble.parse_query_all(parsed_queries)

    latency = []
    q_errors = []
    for i, q in enumerate(queries):
        tic = time.time()
        try:
            pred = bn_ensemble.cardinality(q)
        except:
            # this query itself is invalid or it is not recognizable by the learnt BN
            continue
        latency.append(time.time() - tic)
        if pred is None or pred <= 1:
            pred = 1
        error = max(pred / true[i], true[i] / pred)
        print(f"predicting query no {i}: {real_query[i]} \n")
        print(f"true cardinality {true[i]}, predicted {pred} with q-error {error}")
        q_errors.append(error)
    print("=====================================================================================")
    for i in [50, 90, 95, 99, 100]:
        print(f"q-error {i}% percentile is {np.percentile(q_errors, i)}")
    print(f"average latency is {np.mean(latency)*1000} ms")

    return latency, q_errors

def process_single_query(query_data, bn_ensemble, true_cards):
    query, idx = query_data
    tic = time.time()
    try:
        pred = bn_ensemble.cardinality(query)
    except:
        # this query itself is invalid or it is not recognizable by the learnt BN
        return None
        
    latency = time.time() - tic
    if pred is None or pred <= 1:
        pred = 1
    error = max(pred / true_cards[idx], true_cards[idx] / pred)
    return (latency, error)


def evaluate_cardinality_imdb(schema, model_path, query_path, infer_algo, learning_algo, max_parents):
    ensemble_location = "Benchmark/IMDB/ensemble_loader.pkl"
    #ensemble_location = "Benchmark/IMDB/ensemble_loader_full_imdb.pkl"
    pairwise_rdc_path = "Benchmark/IMDB/pairwise_rdc.pkl"
    parsed_queries, true = prepare_join_queries(ensemble_location, pairwise_rdc_path, query_path,
                                                join_3_rdc_based=False, true_card_exist=True)

    with open(query_path, "rb") as f:
        real_query = f.readlines()
    bn_ensemble = BN_ensemble(schema)
    for i in range(5):
        with open(f"{model_path}/{i}_{learning_algo}_{max_parents}.pkl", "rb") as f:
            bn = pickle.load(f)
            bn.infer_algo = infer_algo
            bn.init_inference_method()
        bn_ensemble.bns[i] = bn

    queries = bn_ensemble.parse_query_all(parsed_queries)

    latency = []
    predictions = []
    for i, q in enumerate(queries):
        tic = time.time()
        try:
            pred = bn_ensemble.cardinality(q)
        except:
            # this query itself is invalid or it is not recognizable by the learnt BN
            continue
        latency.append(time.time() - tic)
        if pred is None or pred <= 1:
            pred = 1
        prediction = pred# / true[i] #, true[i] / pred)
        #print(f"predicting query no {i}: {real_query[i]} \n")
        #print(f"true cardinality {true[i]}, predicted {pred} with q-error {error}")
        predictions.append(prediction)
    #print("=====================================================================================")
    #for i in [50, 90, 95, 99, 100]:
    #    print(f"q-error {i}% percentile is {np.percentile(q_errors, i)}")
    #print(f"average latency is {np.mean(latency)*1000} ms")

    return latency, predictions

    
    

def evaluate_cardinality_imdb_parallel(schema, model_path, query_path, infer_algo, learning_algo, max_parents):
    ensemble_location = "Benchmark/IMDB/ensemble_loader.pkl"
    pairwise_rdc_path = "Benchmark/IMDB/pairwise_rdc.pkl"
    parsed_queries, true = prepare_join_queries(ensemble_location, pairwise_rdc_path, query_path,
                                                join_3_rdc_based=False, true_card_exist=True)

    with open(query_path, "rb") as f:
        real_query = f.readlines()
    bn_ensemble = BN_ensemble(schema)
    for i in range(5):
        with open(f"{model_path}/{i}_{learning_algo}_{max_parents}.pkl", "rb") as f:
            bn = pickle.load(f)
            bn.infer_algo = infer_algo
            bn.init_inference_method()
        bn_ensemble.bns[i] = bn

    queries = bn_ensemble.parse_query_all(parsed_queries)
    
    # Prepare query data with indices
    query_data = list(enumerate(queries))
    
    # Use all available CPU cores except one
    num_processes = max(1, cpu_count() - 1)
    
    start_t = time.time()
    # Create a pool and process queries in parallel
    with Pool(processes=num_processes) as pool:
        # Use partial to fix the bn_ensemble and true parameters
        process_func = partial(process_single_query, bn_ensemble=bn_ensemble, true_cards=true)
        results = pool.map(process_func, query_data)
    end_t = time.time()
    # write the time taken to the log file
    with open("log.txt", "a") as f:
        f.write(f"processing time: {end_t - start_t} seconds\n")
    
    # Filter out None results and separate latencies and errors
    results = [r for r in results if r is not None]
    latency, q_errors = zip(*results) if results else ([], [])
    
    #print("=====================================================================================")
    #for i in [50, 90, 95, 99, 100]:
    #    print(f"q-error {i}% percentile is {np.percentile(q_errors, i)}")
    #print(f"average latency is {np.mean(latency)*1000} ms")

    return latency, q_errors

def evaluate_cardinality_imdb_jobjoin(schema, model_path, query_path, infer_algo, learning_algo, max_parents):
    ensemble_location = "Benchmark/IMDB/ensemble_loader.pkl"
    pairwise_rdc_path = "Benchmark/IMDB/pairwise_rdc.pkl"
    
    parsed_queries, true = prepare_join_queries(ensemble_location, pairwise_rdc_path, query_path,
                                                join_3_rdc_based=False, true_card_exist=True)

    with open(query_path, "rb") as f:
        real_query = f.readlines()
    bn_ensemble = BN_ensemble(schema)
    for i in range(5):
        with open(f"{model_path}/{i}_{learning_algo}_{max_parents}.pkl", "rb") as f:
            bn = pickle.load(f)
            bn.infer_algo = infer_algo
            bn.init_inference_method()
        bn_ensemble.bns[i] = bn

    queries = bn_ensemble.parse_query_all(parsed_queries)

    latency = []
    q_errors = []
    for i, q in enumerate(queries):
        tic = time.time()
        try:
            pred = bn_ensemble.cardinality(q)
        except:
            # this query itself is invalid or it is not recognizable by the learnt BN
            continue
        latency.append(time.time() - tic)
        if pred is None or pred <= 1:
            pred = 1
        error = max(pred / true[i], true[i] / pred)
        print(f"predicting query no {i}: {real_query[i]} \n")
        print(f"true cardinality {true[i]}, predicted {pred} with q-error {error}")
        q_errors.append(error)
    print("=====================================================================================")
    for i in [50, 90, 95, 99, 100]:
        print(f"q-error {i}% percentile is {np.percentile(q_errors, i)}")
    print(f"average latency is {np.mean(latency)*1000} ms")

    return latency, q_errors
